import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme.dart';
import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/config/settings.dart';
import '../../core/providers.dart';
import '../../core/widgets/common.dart';
import '../auth/auth_errors.dart';
import '../history/history_repository.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  bool _checking = false;
  HealthInfo? _health;
  String? _healthError;

  Future<void> _testConnection() async {
    setState(() {
      _checking = true;
      _health = null;
      _healthError = null;
    });
    try {
      final health = await ref.read(apiClientProvider).health();
      if (mounted) setState(() => _health = health);
    } on ApiException catch (e) {
      if (mounted) setState(() => _healthError = e.message);
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _editServerUrl() async {
    final settings = ref.read(settingsProvider);
    final controller = TextEditingController(text: settings.apiBaseUrl);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Analysis server'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: controller,
              autofocus: true,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(labelText: 'URL', hintText: 'http://192.168.1.20:8000'),
            ),
            const SizedBox(height: Insets.sm),
            Text(
              'On a physical phone, use your computer’s LAN address. Leave empty for the default '
              '(${defaultApiBaseUrl()}).',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, ''), child: const Text('Reset')),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Save')),
        ],
      ),
    );
    controller.dispose();
    if (result == null) return;
    await ref.read(settingsProvider.notifier).setApiBaseUrl(result);
    if (!mounted) return;
    setState(() {
      _health = null;
      _healthError = null;
    });
  }

  Future<void> _editName(User user) async {
    final controller = TextEditingController(text: user.displayName ?? '');
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Your name'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Name'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Save')),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.isEmpty) return;
    try {
      await user.updateDisplayName(name);
    } on FirebaseAuthException catch (e) {
      if (mounted) showMessage(context, authErrorMessage(e.code), error: true);
    }
  }

  Future<void> _signOut() async {
    await ref.read(firebaseAuthProvider).signOut();
  }

  Future<void> _deleteAccount(User user) async {
    final password = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete account?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('This permanently deletes your account and all saved analyses. It can’t be undone.'),
            const SizedBox(height: Insets.lg),
            TextField(
              controller: password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Confirm with your password'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    final pw = password.text;
    password.dispose();
    if (confirmed != true) return;

    try {
      // Re-authenticate first: deleting the user requires a recent login, and
      // the data must be deleted while we are still signed in.
      if (user.email != null) {
        await user.reauthenticateWithCredential(
          EmailAuthProvider.credential(email: user.email!, password: pw),
        );
      }
      await ref.read(historyRepositoryProvider)?.deleteAll();
      await user.delete();
    } on FirebaseAuthException catch (e) {
      if (mounted) showMessage(context, authErrorMessage(e.code), error: true);
    } catch (e) {
      if (mounted) showMessage(context, "Couldn't delete your account: $e", error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final settings = ref.watch(settingsProvider);
    final user = ref.watch(authStateProvider).value;
    final name = user?.displayName;
    final initials = (name == null || name.trim().isEmpty)
        ? (user?.email?.substring(0, 1).toUpperCase() ?? '?')
        : name.trim().split(RegExp(r'\s+')).take(2).map((w) => w[0].toUpperCase()).join();

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(Insets.lg, 0, Insets.lg, Insets.xxl),
        children: [
          Card(
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: Insets.lg, vertical: Insets.sm),
              leading: CircleAvatar(
                radius: 24,
                backgroundColor: theme.colorScheme.primary,
                foregroundColor: theme.colorScheme.onPrimary,
                child: Text(initials),
              ),
              title: Text(name?.isNotEmpty == true ? name! : 'Add your name'),
              subtitle: Text(user?.email ?? ''),
              trailing: const Icon(Icons.edit_outlined),
              onTap: user == null ? null : () => _editName(user),
            ),
          ),
          const SectionHeader('Preferences'),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(Insets.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Hitting hand', style: theme.textTheme.titleSmall),
                  const SizedBox(height: Insets.sm),
                  SegmentedButton<Handedness>(
                    segments: const [
                      ButtonSegment(value: Handedness.auto, label: Text('Auto')),
                      ButtonSegment(value: Handedness.right, label: Text('Right')),
                      ButtonSegment(value: Handedness.left, label: Text('Left')),
                    ],
                    selected: {settings.handedness},
                    onSelectionChanged: (s) => ref.read(settingsProvider.notifier).setHandedness(s.first),
                  ),
                  const SizedBox(height: Insets.lg),
                  Text('Appearance', style: theme.textTheme.titleSmall),
                  const SizedBox(height: Insets.sm),
                  SegmentedButton<ThemeMode>(
                    segments: const [
                      ButtonSegment(value: ThemeMode.system, label: Text('System')),
                      ButtonSegment(value: ThemeMode.light, label: Text('Light')),
                      ButtonSegment(value: ThemeMode.dark, label: Text('Dark')),
                    ],
                    selected: {settings.themeMode},
                    onSelectionChanged: (s) => ref.read(settingsProvider.notifier).setThemeMode(s.first),
                  ),
                ],
              ),
            ),
          ),
          const SectionHeader('Analysis server'),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.dns_outlined),
                  title: const Text('Server URL'),
                  subtitle: Text(settings.apiBaseUrl),
                  trailing: const Icon(Icons.edit_outlined),
                  onTap: _editServerUrl,
                ),
                const Divider(height: 1),
                ListTile(
                  leading: _checking
                      ? const SizedBox.square(dimension: 24, child: CircularProgressIndicator(strokeWidth: 2.5))
                      : Icon(
                          _health != null
                              ? Icons.check_circle_rounded
                              : _healthError != null
                                  ? Icons.error_rounded
                                  : Icons.wifi_tethering_rounded,
                          color: _health != null
                              ? context.scores.good
                              : _healthError != null
                                  ? context.scores.needsWork
                                  : null,
                        ),
                  title: const Text('Test connection'),
                  subtitle: _health != null
                      ? Text(
                          'Connected · v${_health!.version ?? '?'}\n'
                          'Pose: ${_health!.poseModel ?? '?'} · Strokes: ${_health!.classifier ?? '?'} · '
                          'Targets: ${_health!.reference ?? '?'}',
                        )
                      : _healthError != null
                          ? Text(_healthError!)
                          : null,
                  isThreeLine: _health != null,
                  onTap: _checking ? null : _testConnection,
                ),
              ],
            ),
          ),
          const SectionHeader('Account'),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.logout_rounded),
                  title: const Text('Sign out'),
                  onTap: _signOut,
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(Icons.delete_forever_rounded, color: theme.colorScheme.error),
                  title: Text('Delete account', style: TextStyle(color: theme.colorScheme.error)),
                  onTap: user == null ? null : () => _deleteAccount(user),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
