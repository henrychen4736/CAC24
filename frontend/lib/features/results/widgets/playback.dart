import 'package:flutter/foundation.dart';
import 'package:video_player/video_player.dart';

/// A playback clock the skeleton overlay can follow at display frame rate.
///
/// `video_player` only reports its position a few times per second, so
/// [VideoPlayback] extrapolates between reports on every [tick]. When there is
/// no video (e.g. the bundled sample), [SyntheticPlayback] drives the clock on
/// its own so the skeleton can still be replayed.
abstract class Playback extends ChangeNotifier {
  Duration get position;
  Duration get duration;
  bool get isPlaying;
  double get speed;

  double get positionSeconds => position.inMicroseconds / 1e6;

  Future<void> play();
  Future<void> pause();
  Future<void> seek(Duration to);
  Future<void> setSpeed(double speed);

  /// Called by a Ticker every display frame.
  void tick(Duration elapsed);

  Future<void> togglePlay() => isPlaying ? pause() : play();

  Future<void> seekSeconds(double s) =>
      seek(Duration(microseconds: (s.clamp(0, duration.inMicroseconds / 1e6) * 1e6).round()));
}

class VideoPlayback extends Playback {
  VideoPlayback(this.controller) {
    controller.addListener(_onVideo);
    _anchor = controller.value.position;
  }

  final VideoPlayerController controller;
  late Duration _anchor;
  Duration? _anchorAt;
  Duration _lastTick = Duration.zero;
  Duration _position = Duration.zero;
  Duration? _pendingSeek;

  @override
  Duration get position => _pendingSeek ?? _position;

  @override
  Duration get duration => controller.value.duration;

  @override
  bool get isPlaying => controller.value.isPlaying;

  @override
  double get speed => controller.value.playbackSpeed;

  void _onVideo() {
    final reported = controller.value.position;
    if (reported != _anchor) {
      _anchor = reported;
      _anchorAt = _lastTick;
      if (_pendingSeek != null && (reported - _pendingSeek!).abs() < const Duration(milliseconds: 250)) {
        _pendingSeek = null;
      }
    }
    if (!isPlaying) _position = reported;
    notifyListeners();
  }

  @override
  void tick(Duration elapsed) {
    _lastTick = elapsed;
    if (!isPlaying || _pendingSeek != null) return;
    _anchorAt ??= elapsed;
    final since = elapsed - _anchorAt!;
    var p = _anchor + since * speed;
    if (p > duration) p = duration;
    _position = p;
    notifyListeners();
  }

  @override
  Future<void> play() async {
    if (position >= duration - const Duration(milliseconds: 50)) {
      await seek(Duration.zero);
    }
    _anchorAt = _lastTick;
    await controller.play();
  }

  @override
  Future<void> pause() async {
    await controller.pause();
    _position = controller.value.position;
    notifyListeners();
  }

  @override
  Future<void> seek(Duration to) async {
    _pendingSeek = to;
    _position = to;
    _anchor = to;
    _anchorAt = _lastTick;
    notifyListeners();
    await controller.seekTo(to);
    _pendingSeek = null;
  }

  @override
  Future<void> setSpeed(double speed) async {
    _anchor = position;
    _anchorAt = _lastTick;
    await controller.setPlaybackSpeed(speed);
    notifyListeners();
  }

  @override
  void dispose() {
    controller.removeListener(_onVideo);
    super.dispose();
  }
}

class SyntheticPlayback extends Playback {
  SyntheticPlayback(this._duration, {this.loop = true});

  final Duration _duration;
  final bool loop;
  Duration _position = Duration.zero;
  Duration? _lastTick;
  bool _playing = false;
  double _speed = 1;

  @override
  Duration get position => _position;

  @override
  Duration get duration => _duration;

  @override
  bool get isPlaying => _playing;

  @override
  double get speed => _speed;

  @override
  void tick(Duration elapsed) {
    final last = _lastTick;
    _lastTick = elapsed;
    if (!_playing || last == null) return;
    var p = _position + (elapsed - last) * _speed;
    if (p >= _duration) {
      if (loop) {
        p = Duration.zero;
      } else {
        p = _duration;
        _playing = false;
      }
    }
    _position = p;
    notifyListeners();
  }

  @override
  Future<void> play() async {
    if (_position >= _duration) _position = Duration.zero;
    _lastTick = null; // the next tick becomes the time base; paused time doesn't count
    _playing = true;
    notifyListeners();
  }

  @override
  Future<void> pause() async {
    _playing = false;
    notifyListeners();
  }

  @override
  Future<void> seek(Duration to) async {
    _position = to < Duration.zero ? Duration.zero : (to > _duration ? _duration : to);
    notifyListeners();
  }

  @override
  Future<void> setSpeed(double speed) async {
    _speed = speed;
    notifyListeners();
  }
}
