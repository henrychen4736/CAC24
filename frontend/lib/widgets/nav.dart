import 'package:flutter/material.dart';
import 'package:tennis_analyze/screens/analyze.dart';
import 'package:tennis_analyze/screens/history.dart';
import 'package:tennis_analyze/screens/home.dart';

class NavigationWrapper extends StatefulWidget {
  final Widget child;

  const NavigationWrapper({super.key, required this.child});

  @override
  NavigationWrapperState createState() => NavigationWrapperState();
}

class NavigationWrapperState extends State<NavigationWrapper> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    const HomeScreen(),
    const AnalyzeScreen(),
    const HistoryScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (int index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.add_a_photo_outlined),
            label: 'Analyze',
          ),
          NavigationDestination(
            icon: Icon(Icons.history),
            label: 'History',
          ),
        ],
      ),
    );
  }
}
