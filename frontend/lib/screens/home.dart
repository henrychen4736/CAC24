import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tennis Pose Analyzer'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          const Icon(Icons.sports_tennis, size: 100, color: Colors.green),
          const SizedBox(height: 20),
          const Text(
            'Welcome to Tennis Pose Analyzer',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 20),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Tip of the Day',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  const Text(
                      'Maintain a relaxed grip on your racket for better control.'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
