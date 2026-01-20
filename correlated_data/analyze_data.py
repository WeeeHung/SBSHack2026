"""
Analyze the correlated_traffic_data.parquet file to understand:
- Data structure and columns
- Data types and missing values
- Correlations between features
- Time series characteristics
- Distribution of speedband values
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
PARQUET_FILE = os.path.join(os.path.dirname(__file__), "correlated_traffic_data.parquet")

def analyze_data():
    """Load and analyze the parquet file."""
    print("=" * 80)
    print("Data Analysis: correlated_traffic_data.parquet")
    print("=" * 80)
    
    if not os.path.exists(PARQUET_FILE):
        print(f"ERROR: File not found: {PARQUET_FILE}")
        return
    
    # Load data
    print("\n1. Loading data...")
    df = pd.read_parquet(PARQUET_FILE)
    print(f"   Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"   File size: {os.path.getsize(PARQUET_FILE) / (1024*1024):.2f} MB")
    
    # Basic info
    print("\n2. Column Information:")
    print(df.info())
    
    print("\n3. First few rows:")
    print(df.head(10))
    
    print("\n4. Data Types:")
    print(df.dtypes)
    
    print("\n5. Missing Values:")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df)) * 100
    missing_df = pd.DataFrame({
        'Missing Count': missing,
        'Missing %': missing_pct
    })
    print(missing_df[missing_df['Missing Count'] > 0])
    
    print("\n6. Basic Statistics:")
    print(df.describe())
    
    # Time analysis
    if 'generated_at' in df.columns:
        print("\n7. Time Series Analysis:")
        df['generated_at'] = pd.to_datetime(df['generated_at'])
        print(f"   Date range: {df['generated_at'].min()} to {df['generated_at'].max()}")
        print(f"   Total time span: {df['generated_at'].max() - df['generated_at'].min()}")
        print(f"   Unique timestamps: {df['generated_at'].nunique()}")
        print(f"   Average records per timestamp: {len(df) / df['generated_at'].nunique():.1f}")
        
        # Time gaps
        df_sorted = df.sort_values('generated_at')
        time_diffs = df_sorted.groupby('LinkID')['generated_at'].diff()
        print(f"\n   Time interval statistics (per link):")
        print(f"   Mean interval: {time_diffs.mean()}")
        print(f"   Median interval: {time_diffs.median()}")
        print(f"   Min interval: {time_diffs.min()}")
        print(f"   Max interval: {time_diffs.max()}")
    
    # Link analysis
    if 'LinkID' in df.columns:
        print("\n8. Link Analysis:")
        print(f"   Unique links: {df['LinkID'].nunique()}")
        print(f"   Records per link (min/max/mean):")
        link_counts = df['LinkID'].value_counts()
        print(f"   Min: {link_counts.min()}, Max: {link_counts.max()}, Mean: {link_counts.mean():.1f}")
        print(f"   Links with <10 records: {(link_counts < 10).sum()}")
        print(f"   Links with <50 records: {(link_counts < 50).sum()}")
        print(f"   Links with >=100 records: {(link_counts >= 100).sum()}")
    
    # Speedband analysis
    if 'speedband' in df.columns:
        print("\n9. Speedband Analysis:")
        speedband_values = df['speedband'].dropna().unique()
        print(f"   Unique speedband values: {sorted(speedband_values)}")
        print(f"   Speedband distribution:")
        print(df['speedband'].value_counts().sort_index())
        print(f"   Missing speedband: {df['speedband'].isnull().sum()} ({df['speedband'].isnull().sum()/len(df)*100:.1f}%)")
        print(f"   Speedband statistics:")
        print(f"   Min: {df['speedband'].min()}, Max: {df['speedband'].max()}, Mean: {df['speedband'].mean():.2f}, Std: {df['speedband'].std():.2f}")
    
    # Rainfall analysis
    if 'rainfall_mm' in df.columns:
        print("\n10. Rainfall Analysis:")
        print(f"   Min: {df['rainfall_mm'].min()}, Max: {df['rainfall_mm'].max()}, Mean: {df['rainfall_mm'].mean():.2f}")
        print(f"   Zero rainfall records: {(df['rainfall_mm'] == 0).sum()} ({(df['rainfall_mm'] == 0).sum()/len(df)*100:.1f}%)")
        print(f"   Non-zero rainfall records: {(df['rainfall_mm'] > 0).sum()} ({(df['rainfall_mm'] > 0).sum()/len(df)*100:.1f}%)")
        print(f"   Rainfall > 1mm: {(df['rainfall_mm'] > 1).sum()} ({(df['rainfall_mm'] > 1).sum()/len(df)*100:.1f}%)")
        print(f"   Rainfall > 5mm: {(df['rainfall_mm'] > 5).sum()} ({(df['rainfall_mm'] > 5).sum()/len(df)*100:.1f}%)")
    
    # Incident analysis
    if 'has_incident' in df.columns:
        print("\n11. Incident Analysis:")
        print(f"   Has incident: {df['has_incident'].sum()} ({df['has_incident'].sum()/len(df)*100:.1f}%)")
        print(f"   No incident: {(~df['has_incident']).sum()} ({(~df['has_incident']).sum()/len(df)*100:.1f}%)")
    
    # Correlation analysis
    print("\n12. Correlation Analysis:")
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) > 1:
        corr_matrix = df[numeric_cols].corr()
        print("\n   Full correlation matrix:")
        print(corr_matrix)
        
        # Focus on speedband correlations
        if 'speedband' in corr_matrix.columns:
            print("\n   Correlations with speedband:")
            speedband_corr = corr_matrix['speedband'].sort_values(ascending=False, key=abs)
            for col, corr in speedband_corr.items():
                if col != 'speedband':
                    print(f"   {col}: {corr:.4f}")
    
    # Time series patterns per link
    if 'LinkID' in df.columns and 'generated_at' in df.columns and 'speedband' in df.columns:
        print("\n13. Time Series Patterns (sample of 5 links):")
        sample_links = df['LinkID'].unique()[:5]
        for link_id in sample_links:
            link_data = df[df['LinkID'] == link_id].sort_values('generated_at')
            if len(link_data) > 1:
                print(f"\n   Link {link_id}:")
                print(f"   Records: {len(link_data)}")
                print(f"   Speedband range: {link_data['speedband'].min()} - {link_data['speedband'].max()}")
                print(f"   Speedband changes: {(link_data['speedband'].diff() != 0).sum()}")
                if len(link_data) >= 3:
                    print(f"   Last 3 speedbands: {link_data['speedband'].tail(3).tolist()}")
                    print(f"   Last 3 timestamps: {link_data['generated_at'].tail(3).tolist()}")
    
    # Check for sufficient data for time series modeling
    print("\n14. Data Sufficiency for Time Series Modeling:")
    if 'LinkID' in df.columns and 'generated_at' in df.columns:
        df['generated_at'] = pd.to_datetime(df['generated_at'])
        link_stats = df.groupby('LinkID').agg({
            'generated_at': ['count', 'min', 'max'],
            'speedband': ['count', 'nunique']
        })
        link_stats.columns = ['total_records', 'first_timestamp', 'last_timestamp', 'speedband_count', 'unique_speedbands']
        link_stats['time_span_days'] = (link_stats['last_timestamp'] - link_stats['first_timestamp']).dt.total_seconds() / 86400
        
        print(f"   Links with >= 10 records: {(link_stats['total_records'] >= 10).sum()}")
        print(f"   Links with >= 50 records: {(link_stats['total_records'] >= 50).sum()}")
        print(f"   Links with >= 100 records: {(link_stats['total_records'] >= 100).sum()}")
        print(f"   Links with >= 1 day of data: {(link_stats['time_span_days'] >= 1).sum()}")
        print(f"   Links with >= 7 days of data: {(link_stats['time_span_days'] >= 7).sum()}")
    
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)
    
    return df

if __name__ == "__main__":
    df = analyze_data()
