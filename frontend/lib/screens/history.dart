import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  HistoryScreenState createState() => HistoryScreenState();
}

class HistoryScreenState extends State<HistoryScreen> {
  // This would typically come from your backend or local storage
  final List<Map<String, dynamic>> _analysisHistory = [
    {
      "id": "1",
      "date": DateTime.now().subtract(const Duration(days: 1)),
      "category": "forehand",
      "pose": "forehand_follow_through",
      "similarity_score": 0.85,
      "suggestions": [
        "increase left arm angle by about 5.2 degrees",
        "decrease right arm angle by about 3.7 degrees",
      ],
    },
    {
      "id": "2",
      "date": DateTime.now().subtract(const Duration(days: 3)),
      "category": "backhand",
      "pose": "backhand_preparation",
      "similarity_score": 0.78,
      "suggestions": [
        "increase knees angle by about 7.1 degrees",
        "decrease hips angle by about 4.5 degrees",
      ],
    },
    // Add more history items as needed
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Analysis History'),
      ),
      body: ListView.builder(
        itemCount: _analysisHistory.length,
        itemBuilder: (context, index) {
          final analysis = _analysisHistory[index];
          return Card(
            margin: const EdgeInsets.all(8.0),
            child: ListTile(
              title: Text('${analysis['category']} - ${analysis['pose']}'),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                      'Date: ${DateFormat('yyyy-MM-dd HH:mm').format(analysis['date'])}'),
                  Text(
                      'Similarity Score: ${(analysis['similarity_score'] * 100).toStringAsFixed(1)}%'),
                ],
              ),
              trailing: Icon(
                Icons.circle,
                color: _getScoreColor(analysis['similarity_score']),
              ),
              onTap: () => _showAnalysisDetails(context, analysis),
            ),
          );
        },
      ),
    );
  }

  Color _getScoreColor(double score) {
    if (score >= 0.8) return Colors.green;
    if (score >= 0.6) return Colors.orange;
    return Colors.red;
  }

  void _showAnalysisDetails(
      BuildContext context, Map<String, dynamic> analysis) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('${analysis['category']} - ${analysis['pose']}'),
          content: SingleChildScrollView(
            child: ListBody(
              children: <Widget>[
                Text(
                    'Date: ${DateFormat('yyyy-MM-dd HH:mm').format(analysis['date'])}'),
                Text(
                    'Similarity Score: ${(analysis['similarity_score'] * 100).toStringAsFixed(1)}%'),
                const SizedBox(height: 10),
                const Text('Suggestions:',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                ...analysis['suggestions']
                    .map((suggestion) => Text('• $suggestion'))
                    .toList(),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('Close'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }
}
