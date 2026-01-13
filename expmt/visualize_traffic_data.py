"""
Visualize Traffic Speed Band data over time
Shows speed changes for the first 10 LinkIDs
"""
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# Configuration
INPUT_FILE = "traffic_speed_data.json"
NUM_LINKS = 20  # Number of LinkIDs to visualize (used if MIN_LINK and MAX_LINK are None)
MIN_LINK = 30  # Minimum LinkID to include (None = start from beginning)
MAX_LINK = 50  # Maximum LinkID to include (None = use NUM_LINKS instead)


def load_traffic_data(filename):
    """Load traffic data from JSON file"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Data file '{filename}' not found. Run collect_traffic_data.py first.")
    
    with open(filename, 'r') as f:
        data = json.load(f)
    
    return data


def process_data_for_visualization(data, num_links=10, min_link=None, max_link=None):
    """
    Process data for visualization
    Returns a dictionary with LinkID as key and list of (timestamp, speed) tuples
    
    Args:
        data: Dictionary with LinkID as keys
        num_links: Number of links to process (used if min_link and max_link are None)
        min_link: Minimum LinkID to include (None = start from beginning)
        max_link: Maximum LinkID to include (None = use num_links instead)
    """
    # Determine which link IDs to process
    if min_link is not None or max_link is not None:
        # Use range-based selection
        # Convert all link IDs to integers for comparison (they might be strings in JSON)
        all_link_ids = []
        for link_id in data.keys():
            try:
                all_link_ids.append(int(link_id))
            except (ValueError, TypeError):
                # Skip non-numeric link IDs
                continue
        
        all_link_ids.sort()
        
        if min_link is None:
            min_link = all_link_ids[0] if all_link_ids else 0
        if max_link is None:
            max_link = all_link_ids[-1] if all_link_ids else 0
        
        # Filter link IDs within the range (convert back to original format)
        link_ids = [str(link_id) for link_id in all_link_ids 
                   if min_link <= link_id <= max_link]
    else:
        # Use first N links (original behavior)
        link_ids = list(data.keys())[:num_links]
    
    print(f"Processing {len(link_ids)} links: {link_ids[0] if link_ids else 'N/A'} to {link_ids[-1] if link_ids else 'N/A'}")
    
    processed_data = {}
    
    for link_id in link_ids:
        entries = data[link_id]
        speed_data = []
        
        for entry in entries:
            timestamp_str = entry.get('timestamp')
            # Use average speed (midpoint of min and max)
            min_speed = entry.get('minspeed')
            max_speed = entry.get('maxspeed')
            
            if timestamp_str and min_speed is not None and max_speed is not None:
                try:
                    # Parse timestamp - handle ISO format with microseconds
                    try:
                        # Try parsing with fromisoformat first (Python 3.7+)
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        # Fallback: parse manually if fromisoformat fails
                        # Format: "2026-01-13T15:00:52.462434"
                        if 'T' in timestamp_str:
                            date_part, time_part = timestamp_str.split('T')
                            if '.' in time_part:
                                time_part, microsecond = time_part.split('.')
                                microsecond = int(microsecond.ljust(6, '0')[:6])
                            else:
                                microsecond = 0
                            year, month, day = map(int, date_part.split('-'))
                            hour, minute, second = map(int, time_part.split(':'))
                            timestamp = datetime(year, month, day, hour, minute, second, microsecond)
                        else:
                            raise ValueError(f"Unexpected timestamp format: {timestamp_str}")
                    
                    # Convert speeds to float (handle both string and numeric values)
                    try:
                        min_speed_float = float(min_speed)
                        max_speed_float = float(max_speed)
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Skipping entry with invalid speed values: {e}")
                        continue
                    
                    # Calculate average speed
                    avg_speed = (min_speed_float + max_speed_float) / 2
                    speed_data.append((timestamp, avg_speed, min_speed_float, max_speed_float))
                except (ValueError, TypeError) as e:
                    print(f"Warning: Skipping entry with invalid timestamp or speed: {e}")
                    continue
        
        # Sort by timestamp
        speed_data.sort(key=lambda x: x[0])
        processed_data[link_id] = speed_data
    
    return processed_data


def create_visualization(processed_data, output_file="traffic_speed_visualization.png"):
    """
    Create visualization showing speed changes over time for multiple LinkIDs
    """
    if not processed_data:
        print("No data to visualize")
        return
    
    # Create figure with subplots
    fig, axes = plt.subplots(len(processed_data), 1, figsize=(14, 3 * len(processed_data)))
    
    # If only one link, axes is not a list
    if len(processed_data) == 1:
        axes = [axes]
    
    fig.suptitle('Traffic Speed Changes Over Time (First 10 LinkIDs)', fontsize=16, fontweight='bold')
    
    for idx, (link_id, speed_data) in enumerate(processed_data.items()):
        if not speed_data:
            axes[idx].text(0.5, 0.5, f'LinkID {link_id}: No data', 
                          ha='center', va='center', transform=axes[idx].transAxes)
            axes[idx].set_title(f'LinkID: {link_id}')
            continue
        
        # Extract data
        timestamps = [x[0] for x in speed_data]
        avg_speeds = [x[1] for x in speed_data]
        min_speeds = [x[2] for x in speed_data]
        max_speeds = [x[3] for x in speed_data]
        
        # Plot average speed line
        axes[idx].plot(timestamps, avg_speeds, 'b-', linewidth=2, label='Average Speed', marker='o', markersize=4)
        
        # Plot shaded area for min-max range
        axes[idx].fill_between(timestamps, min_speeds, max_speeds, alpha=0.3, color='lightblue', label='Speed Range')
        
        # Formatting
        axes[idx].set_title(f'LinkID: {link_id}', fontsize=12, fontweight='bold')
        axes[idx].set_xlabel('Time', fontsize=10)
        axes[idx].set_ylabel('Speed (km/h)', fontsize=10)
        axes[idx].grid(True, alpha=0.3)
        axes[idx].legend(loc='upper right')
        
        # Rotate x-axis labels for better readability
        axes[idx].tick_params(axis='x', rotation=45)
        
        # Format x-axis to show time nicely using matplotlib date formatter
        if len(timestamps) > 1:
            axes[idx].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            axes[idx].xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Visualization saved to: {output_file}")
    plt.show()


def create_combined_visualization(processed_data, output_file="traffic_speed_combined.png"):
    """
    Create a single plot with all LinkIDs overlaid
    """
    if not processed_data:
        print("No data to visualize")
        return
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    colors = plt.cm.tab20(range(len(processed_data)))
    
    for idx, (link_id, speed_data) in enumerate(processed_data.items()):
        if not speed_data:
            continue
        
        timestamps = [x[0] for x in speed_data]
        avg_speeds = [x[1] for x in speed_data]
        
        ax.plot(timestamps, avg_speeds, 'o-', linewidth=1.5, markersize=3, 
               label=f'LinkID {link_id}', color=colors[idx], alpha=0.7)
    
    ax.set_title('Traffic Speed Changes Over Time - All LinkIDs', fontsize=16, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Average Speed (km/h)', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=1)
    ax.tick_params(axis='x', rotation=45)
    
    # Format x-axis to show time nicely using matplotlib date formatter
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Combined visualization saved to: {output_file}")
    plt.show()


def print_summary_statistics(processed_data):
    """Print summary statistics for the data"""
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)
    
    for link_id, speed_data in processed_data.items():
        if not speed_data:
            print(f"\nLinkID {link_id}: No data")
            continue
        
        speeds = [x[1] for x in speed_data]  # Average speeds
        timestamps = [x[0] for x in speed_data]
        
        print(f"\nLinkID {link_id}:")
        print(f"  Data points: {len(speed_data)}")
        print(f"  Time range: {timestamps[0].strftime('%Y-%m-%d %H:%M:%S')} to {timestamps[-1].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Average speed: {sum(speeds)/len(speeds):.2f} km/h")
        print(f"  Min speed: {min(speeds):.2f} km/h")
        print(f"  Max speed: {max(speeds):.2f} km/h")
        print(f"  Speed range: {max(speeds) - min(speeds):.2f} km/h")


def main():
    """Main function to visualize traffic data"""
    print("=" * 60)
    print("Traffic Speed Data Visualization")
    print("=" * 60)
    
    try:
        # Load data
        print(f"Loading data from {INPUT_FILE}...")
        data = load_traffic_data(INPUT_FILE)
        print(f"Loaded data for {len(data)} LinkIDs")
        
        # Process data based on configuration
        if MIN_LINK is not None or MAX_LINK is not None:
            print(f"\nProcessing data for LinkIDs in range: {MIN_LINK or 'start'} to {MAX_LINK or 'end'}...")
            processed_data = process_data_for_visualization(data, NUM_LINKS, MIN_LINK, MAX_LINK)
        else:
            print(f"\nProcessing data for first {NUM_LINKS} LinkIDs...")
            processed_data = process_data_for_visualization(data, NUM_LINKS)
        
        # Print summary statistics
        print_summary_statistics(processed_data)
        
        # Create visualizations
        print("\n" + "=" * 60)
        print("Creating visualizations...")
        print("=" * 60)
        
        # Individual subplots
        create_visualization(processed_data, "traffic_speed_individual.png")
        
        # Combined plot
        create_combined_visualization(processed_data, "traffic_speed_combined.png")
        
        print("\nVisualization complete!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
