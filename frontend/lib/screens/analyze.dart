import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:video_player/video_player.dart';

class AnalysisStats {
  final double overallSimilarity;
  final Map<String, double> jointSimilarities;

  AnalysisStats({
    required this.overallSimilarity,
    required this.jointSimilarities,
  });

  factory AnalysisStats.fromJson(Map<String, dynamic> json) {
    return AnalysisStats(
      overallSimilarity: json['overall_similarity'].toDouble(),
      jointSimilarities: Map<String, double>.from(json['joint_similarities']),
    );
  }
}

class AnalyzeScreen extends StatefulWidget {
  const AnalyzeScreen({super.key});

  @override
  AnalyzeScreenState createState() => AnalyzeScreenState();
}

class AnalyzeScreenState extends State<AnalyzeScreen> {
  String? _selectedStroke;
  File? _video;
  final ImagePicker _picker = ImagePicker();
  String _analysisResult = '';
  VideoPlayerController? _videoController;
  AnalysisStats? _stats;
  bool _isAnalyzing = false;

  final List<String> _strokeTypes = [
    'Backhand',
    'Forehand',
    'Kick Serve',
  ];

  Future<void> _getVideo(ImageSource source) async {
    final XFile? pickedFile = await _picker.pickVideo(source: source);

    setState(() {
      if (pickedFile != null) {
        _video = File(pickedFile.path);
        _analysisResult = '';
        _stats = null;
      }
    });
  }

  Future<void> _analyzeVideo() async {
    if (_video == null || _selectedStroke == null) return;

    setState(() {
      _isAnalyzing = true;
    });

    String baseUrl;
    if (Platform.isAndroid) {
      baseUrl = 'http://10.0.2.2:5001';
    } else if (Platform.isIOS) {
      baseUrl = 'http://localhost:5001';
    } else if (Platform.isWindows) {
      baseUrl = 'http://localhost:5001';
    } else {
      throw Exception('Unsupported platform');
    }

    String endpoint =
        '/analyze_shot_${_selectedStroke!.toLowerCase().replaceAll(' ', '')}';
    final uri = Uri.parse('$baseUrl$endpoint');

    try {
      var request = http.MultipartRequest('POST', uri);
      request.files
          .add(await http.MultipartFile.fromPath('file', _video!.path));

      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse)
          .timeout(const Duration(minutes: 5));

      if (response.statusCode == 200) {
        String? statsJson = response.headers['x-analysis-stats'];
        if (statsJson != null) {
          setState(() {
            _stats = AnalysisStats.fromJson(jsonDecode(statsJson));
          });
        }

        await _saveAndPlayVideo(response.bodyBytes);
      } else {
        setState(() {
          _analysisResult = 'Error: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _analysisResult = 'Error: $e';
      });
    } finally {
      setState(() {
        _isAnalyzing = false;
      });
    }
  }

  Future<void> _saveAndPlayVideo(Uint8List videoBytes) async {
    final directory = await getApplicationDocumentsDirectory();
    final videoPath = '${directory.path}/annotated_video.mp4';
    final videoFile = File(videoPath);

    await videoFile.writeAsBytes(videoBytes);

    _videoController = VideoPlayerController.file(videoFile)
      ..initialize().then((_) {
        setState(() {
          _videoController?.play();
        });
      });
  }

  @override
  void dispose() {
    _videoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Theme.of(context).scaffoldBackgroundColor,
        title: Text(
          'Tennis Stroke Analysis',
          style: TextStyle(
            color: Theme.of(context).primaryColor,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_videoController != null &&
                _videoController!.value.isInitialized) ...[
              Container(
                height: MediaQuery.of(context).size.height * 0.4,
                decoration: BoxDecoration(
                  color: Colors.black,
                ),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    AspectRatio(
                      aspectRatio: _videoController!.value.aspectRatio,
                      child: VideoPlayer(_videoController!),
                    ),
                    Positioned(
                      bottom: 16,
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.black45,
                          borderRadius: BorderRadius.circular(30),
                        ),
                        child: IconButton(
                          icon: Icon(
                            _videoController!.value.isPlaying
                                ? Icons.pause
                                : Icons.play_arrow,
                            color: Colors.white,
                            size: 32,
                          ),
                          onPressed: () {
                            setState(() {
                              _videoController!.value.isPlaying
                                  ? _videoController!.pause()
                                  : _videoController!.play();
                            });
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            Container(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: Theme.of(context).cardColor,
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.05),
                          blurRadius: 10,
                          offset: Offset(0, 4),
                        ),
                      ],
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        isExpanded: true,
                        value: _selectedStroke,
                        hint: Text(
                          'Select Tennis Stroke',
                          style: TextStyle(
                            color: Theme.of(context).hintColor,
                            fontSize: 16,
                          ),
                        ),
                        items: _strokeTypes.map((String value) {
                          return DropdownMenuItem<String>(
                            value: value,
                            child: Text(
                              value,
                              style: TextStyle(fontSize: 16),
                            ),
                          );
                        }).toList(),
                        onChanged: (newValue) {
                          setState(() {
                            _selectedStroke = newValue;
                          });
                        },
                      ),
                    ),
                  ),
                  SizedBox(height: 24),
                  Row(
                    children: [
                      Expanded(
                        child: _buildActionButton(
                          icon: Icons.video_library,
                          label: 'Gallery',
                          onPressed: () => _getVideo(ImageSource.gallery),
                        ),
                      ),
                      SizedBox(width: 16),
                      Expanded(
                        child: _buildActionButton(
                          icon: Icons.videocam,
                          label: 'Camera',
                          onPressed: () => _getVideo(ImageSource.camera),
                        ),
                      ),
                    ],
                  ),
                  if (_video != null) ...[
                    SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        foregroundColor: Colors.white,
                        backgroundColor: Theme.of(context).primaryColor,
                        padding: EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        elevation: 2,
                      ),
                      onPressed: _selectedStroke != null && !_isAnalyzing
                          ? _analyzeVideo
                          : null,
                      child: _isAnalyzing
                          ? Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                        Colors.white),
                                  ),
                                ),
                                SizedBox(width: 12),
                                Text(
                                  'Analyzing...',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            )
                          : Text(
                              'Analyze Video',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                    ),
                  ],
                  if (_stats != null) ...[
                    SizedBox(height: 24),
                    _buildAnalysisResults(),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
  }) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        foregroundColor: Colors.white,
        backgroundColor: Theme.of(context).primaryColor,
        padding: EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        elevation: 2,
      ),
      onPressed: onPressed,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 24),
          SizedBox(height: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalysisResults() {
    return Container(
      padding: EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Analysis Results',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Theme.of(context).textTheme.titleLarge?.color,
            ),
          ),
          SizedBox(height: 16),
          _buildScoreIndicator(
            'Overall Similarity',
            _stats!.overallSimilarity,
            isPrimary: true,
          ),
          SizedBox(height: 20),
          Text(
            'Joint Analysis',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Theme.of(context).textTheme.titleMedium?.color,
            ),
          ),
          SizedBox(height: 12),
          ..._stats!.jointSimilarities.entries.map((entry) {
            final formattedJoint = entry.key
                .split('_')
                .map((word) => word[0].toUpperCase() + word.substring(1))
                .join(' ');
            return Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: _buildScoreIndicator(formattedJoint, entry.value),
            );
          }).toList(),
        ],
      ),
    );
  }

  Widget _buildScoreIndicator(String label, double value,
      {bool isPrimary = false}) {
    final percentage = (value * 100).toStringAsFixed(1);
    final color = isPrimary
        ? Theme.of(context).primaryColor
        : HSLColor.fromColor(Theme.of(context).primaryColor)
            .withLightness(0.4)
            .toColor();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: isPrimary ? 16 : 14,
                fontWeight: isPrimary ? FontWeight.w600 : FontWeight.normal,
                color: Theme.of(context).textTheme.bodyLarge?.color,
              ),
            ),
            Text(
              '$percentage%',
              style: TextStyle(
                fontSize: isPrimary ? 16 : 14,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
        SizedBox(height: 8),
        LinearProgressIndicator(
          value: value,
          backgroundColor: color.withOpacity(0.2),
          valueColor: AlwaysStoppedAnimation<Color>(color),
          minHeight: isPrimary ? 8 : 6,
          borderRadius: BorderRadius.circular(4),
        ),
      ],
    );
  }
}
