"""
Log viewer utility for drone simulator.
This script provides a convenient way to view and filter logs.
"""
# filepath: /Users/trishit_debsharma/Documents/Code/Mechatronic/software_round2/tools/log_viewer.py
import os
import sys
import argparse
import glob
from datetime import datetime, timedelta
import re

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_logs_directory():
    """Get the path to the logs directory."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "logs")

def list_log_files():
    """List all available log files."""
    logs_dir = get_logs_directory()
    if not os.path.exists(logs_dir):
        print(f"Logs directory not found: {logs_dir}")
        return []
    
    log_files = glob.glob(os.path.join(logs_dir, "*.log"))
    return sorted(log_files)

def parse_log_line(line):
    """Parse a log line into timestamp and content."""
    # Expected format: 2025-04-01 10:42:18,123 - ...
    timestamp_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"
    match = re.match(timestamp_pattern, line)
    
    if match:
        timestamp_str = match.group(1)
        content = line[match.end():]
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            return timestamp, content
        except ValueError:
            pass
    
    return None, line

def filter_log_by_time(file_path, hours=None, minutes=None):
    """Filter log entries by time (entries within the last N hours/minutes)."""
    if not os.path.exists(file_path):
        print(f"Log file not found: {file_path}")
        return []
    
    cutoff_time = None
    if hours is not None:
        cutoff_time = datetime.now() - timedelta(hours=hours)
    elif minutes is not None:
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
    
    filtered_lines = []
    with open(file_path, 'r') as f:
        for line in f:
            timestamp, content = parse_log_line(line)
            
            # If no time filter or we couldn't parse the timestamp, include all lines
            if cutoff_time is None or timestamp is None:
                filtered_lines.append(line.strip())
            # Otherwise, only include lines after the cutoff time
            elif timestamp >= cutoff_time:
                filtered_lines.append(line.strip())
    
    return filtered_lines

def filter_log_by_level(lines, level=None):
    """Filter log entries by level."""
    if level is None:
        return lines
    
    level = level.upper()
    filtered_lines = []
    
    for line in lines:
        if f"[{level}]" in line:
            filtered_lines.append(line)
    
    return filtered_lines

def filter_log_by_text(lines, text=None):
    """Filter log entries containing specific text."""
    if text is None:
        return lines
    
    filtered_lines = []
    for line in lines:
        if text.lower() in line.lower():
            filtered_lines.append(line)
    
    return filtered_lines

def main():
    """Run the log viewer."""
    parser = argparse.ArgumentParser(description="Drone Simulator Log Viewer")
    parser.add_argument("--file", help="Specific log file to view")
    parser.add_argument("--list", action="store_true", help="List available log files")
    parser.add_argument("--hours", type=int, help="Show logs from last N hours")
    parser.add_argument("--minutes", type=int, help="Show logs from last N minutes")
    parser.add_argument("--level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Filter by log level")
    parser.add_argument("--text", help="Filter logs containing this text")
    parser.add_argument("--tail", type=int, help="Show only the last N lines")
    
    args = parser.parse_args()
    
    if args.list:
        log_files = list_log_files()
        if log_files:
            print("Available log files:")
            for i, log_file in enumerate(log_files, 1):
                filename = os.path.basename(log_file)
                size = os.path.getsize(log_file) / 1024  # KB
                modified = datetime.fromtimestamp(os.path.getmtime(log_file))
                print(f"{i}. {filename} ({size:.1f} KB) - Last modified: {modified}")
        else:
            print("No log files found")
        return
    
    # If no specific file is provided, try to list files
    if not args.file:
        log_files = list_log_files()
        if not log_files:
            print("No log files found")
            return
        
        print("Please specify a log file with --file option. Available files:")
        for i, log_file in enumerate(log_files, 1):
            print(f"{i}. {os.path.basename(log_file)}")
        return
    
    # Check if the file exists
    file_path = args.file
    if not os.path.isabs(file_path):
        # Try to find it in the logs directory
        logs_dir = get_logs_directory()
        potential_path = os.path.join(logs_dir, file_path)
        if os.path.exists(potential_path):
            file_path = potential_path
    
    if not os.path.exists(file_path):
        print(f"Log file not found: {file_path}")
        return
    
    # Apply filters
    lines = filter_log_by_time(file_path, args.hours, args.minutes)
    lines = filter_log_by_level(lines, args.level)
    lines = filter_log_by_text(lines, args.text)
    
    # Apply tail if needed
    if args.tail and len(lines) > args.tail:
        lines = lines[-args.tail:]
    
    # Print results
    if lines:
        print(f"Showing logs from {file_path}:")
        print("-" * 80)
        for line in lines:
            print(line)
        print("-" * 80)
        print(f"Total lines: {len(lines)}")
    else:
        print("No matching log entries found")

if __name__ == "__main__":
    main()