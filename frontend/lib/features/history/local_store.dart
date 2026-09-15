import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

import '../results/models/report.dart';

/// Device-local files for an analysis: a copy of the video and the pose track
/// (both too large for Firestore). Layout: `<documents>/analyses/<id>/`.
class LocalAnalysisStore {
  LocalAnalysisStore({Future<Directory> Function()? baseDir})
      : _baseDir = baseDir ?? getApplicationDocumentsDirectory;

  final Future<Directory> Function() _baseDir;

  Future<Directory> _root() async => Directory('${(await _baseDir()).path}/analyses');

  Future<Directory> _dir(String id, {bool create = false}) async {
    final dir = Directory('${(await _root()).path}/$id');
    if (create) await dir.create(recursive: true);
    return dir;
  }

  /// Copies [sourcePath] into the store and returns the new path.
  Future<String> saveVideo(String id, String sourcePath) async {
    final dir = await _dir(id, create: true);
    final name = sourcePath.split(RegExp(r'[\\/]')).last;
    final ext = name.contains('.') ? name.split('.').last.toLowerCase() : 'mp4';
    final dest = '${dir.path}/video.$ext';
    if (sourcePath != dest) await File(sourcePath).copy(dest);
    return dest;
  }

  Future<void> savePoseTrack(String id, PoseTrack track) async {
    final dir = await _dir(id, create: true);
    await File('${dir.path}/pose_track.json').writeAsString(jsonEncode(track.toJson()));
  }

  Future<PoseTrack?> loadPoseTrack(String id) async {
    final file = File('${(await _dir(id)).path}/pose_track.json');
    if (!await file.exists()) return null;
    try {
      return PoseTrack.fromJson(jsonDecode(await file.readAsString()) as Map<String, dynamic>);
    } on FormatException {
      return null;
    }
  }

  Future<String?> findVideo(String id) async {
    final dir = await _dir(id);
    if (!await dir.exists()) return null;
    await for (final e in dir.list()) {
      if (e is File && e.uri.pathSegments.last.startsWith('video.')) return e.path;
    }
    return null;
  }

  Future<void> delete(String id) async {
    final dir = await _dir(id);
    if (await dir.exists()) await dir.delete(recursive: true);
  }

  Future<void> deleteAll() async {
    final root = await _root();
    if (await root.exists()) await root.delete(recursive: true);
  }
}
