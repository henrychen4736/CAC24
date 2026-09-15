import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/api_client.dart';
import 'config/settings.dart';

final firebaseAuthProvider = Provider<FirebaseAuth>((ref) => FirebaseAuth.instance);

final firestoreProvider = Provider<FirebaseFirestore>((ref) => FirebaseFirestore.instance);

/// Signed-in user; also emits on profile changes (display name, etc.).
final authStateProvider = StreamProvider<User?>(
  (ref) => ref.watch(firebaseAuthProvider).userChanges(),
);

final idTokenProvider = Provider<TokenProvider>((ref) {
  final auth = ref.watch(firebaseAuthProvider);
  return () async => auth.currentUser?.getIdToken();
});

final apiClientProvider = Provider<TennisApi>((ref) {
  final baseUrl = ref.watch(settingsProvider.select((s) => s.apiBaseUrl));
  return TennisApi(baseUrl: baseUrl, tokenProvider: ref.watch(idTokenProvider));
});
