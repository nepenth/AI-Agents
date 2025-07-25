# JSON to Database Migration - User Guide

## Table of Contents
- [Getting Started](#getting-started)
- [Tweet Management Interface](#tweet-management-interface)
- [Search and Filtering](#search-and-filtering)
- [Tweet Details and Actions](#tweet-details-and-actions)
- [Bulk Operations](#bulk-operations)
- [Statistics and Analytics](#statistics-and-analytics)
- [Common Workflows](#common-workflows)
- [Tips and Best Practices](#tips-and-best-practices)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Accessing the Tweet Management Interface

1. **Navigate to the Web Interface**
   - Open your web browser
   - Go to `http://localhost:5000/v2/page/tweets` (or your configured host/port)
   - The interface will load with the latest tweets

2. **Interface Overview**
   - **Header**: Search bar and quick filters
   - **Main Table**: Tweet listing with status indicators
   - **Sidebar**: Advanced filters and statistics
   - **Footer**: Pagination controls

### Initial Setup

The Tweet Management interface requires no initial setup - it automatically connects to your migrated database and displays available tweets. If you're seeing an empty interface, ensure:
- The migration has been completed successfully
- The database contains tweet data
- The Knowledge Base Agent is running

## Tweet Management Interface

### Main Dashboard

The Tweet Management dashboard provides a comprehensive view of your tweet collection with powerful management capabilities.

#### Header Section
- **Search Bar**: Full-text search across tweet content
- **Quick Filters**: Instant filtering by common criteria
- **Results Summary**: Shows current view statistics
- **Action Buttons**: Access to bulk operations and statistics

#### Tweet Table

The main table displays tweets with the following columns:

| Column | Description | Actions |
|--------|-------------|---------|
| **Selection** | Checkbox for bulk operations | Click to select/deselect tweets |
| **Tweet ID** | Unique Twitter identifier | Click to view details |
| **Cache Status** | Processing completion indicator | Green (Complete) / Red (Incomplete) |
| **Media Status** | Media processing indicator | Green (Processed) / Red (Pending) |
| **Content Preview** | First 100 characters of tweet text | Hover for tooltip |
| **Created Date** | When tweet was first cached | Sortable column |
| **Updated Date** | Last modification timestamp | Sortable column |
| **Actions** | Quick action buttons | View Details, Reprocess |

#### Status Indicators

**Cache Status Badges:**
- 🟢 **Complete**: Tweet has been fully cached and processed
- 🔴 **Incomplete**: Tweet caching is pending or failed
- 🟡 **Processing**: Tweet is currently being processed

**Media Status Badges:**
- 🟢 **Processed**: All media files have been downloaded and processed
- 🔴 **Pending**: Media processing is queued or failed
- 🟡 **Processing**: Media is currently being downloaded

## Search and Filtering

### Full-Text Search

The search functionality provides powerful content discovery:

1. **Basic Search**
   ```
   Enter keywords in the search bar
   Example: "machine learning" or "AI"
   ```

2. **Search Features**
   - **Real-time results**: Updates as you type (300ms delay)
   - **Case-insensitive**: Searches regardless of capitalization
   - **Partial matching**: Finds tweets containing any part of your search terms
   - **Unicode support**: Works with emojis and international characters

3. **Search Tips**
   - Use quotes for exact phrases: `"artificial intelligence"`
   - Multiple keywords return tweets containing any of the terms
   - Special characters are automatically escaped

### Quick Filters

Located in the header for instant access:

#### Cache Complete Filter
- **All**: Show tweets regardless of cache status
- **Complete**: Only fully cached tweets
- **Incomplete**: Only tweets pending cache completion

#### Media Processed Filter
- **All**: Show tweets regardless of media status
- **Processed**: Only tweets with processed media
- **Pending**: Only tweets with pending media processing

#### Category Filter
- **All**: Show tweets from all categories
- **Specific Category**: Filter by main category (Technology, Science, etc.)

### Advanced Filters

Access via the sidebar panel for detailed filtering:

#### Date Range Filters
```
Created Date:
- From: [Date Picker]
- To: [Date Picker]

Updated Date:
- From: [Date Picker] 
- To: [Date Picker]
```

#### Processing Status Filters
```
☐ Cache Complete
☐ Cache Incomplete
☐ Media Processed
☐ Media Pending
☐ Recently Updated (Last 24h)
☐ Stale Tweets (>7 days)
```

#### Content Filters
```
Has Media: [Yes/No/Any]
Has Links: [Yes/No/Any]
Has Mentions: [Yes/No/Any]
Has Hashtags: [Yes/No/Any]
```

### Sorting Options

Click column headers to sort:

#### Available Sort Fields
- **Created Date** (Default: Newest first)
- **Updated Date**
- **Tweet ID** (Alphanumeric)

#### Sort Orders
- **Ascending** (↑): Oldest/lowest first
- **Descending** (↓): Newest/highest first

## Tweet Details and Actions

### Viewing Tweet Details

1. **Access Details**
   - Click the "View Details" button in the Actions column
   - Or click directly on the Tweet ID

2. **Detail Modal Contents**

#### Basic Information
```
Tweet ID: 1234567890123456789
Created: January 15, 2024 10:30 AM
Updated: January 15, 2024 11:45 AM
Status: Cache Complete, Media Processed
```

#### Content Data
- **Full Tweet Text**: Complete original tweet content
- **User Information**: Author details and follower count
- **Media Files**: List of images, videos, and their processing status
- **Links**: Extracted URLs and their metadata
- **Hashtags**: All hashtags found in the tweet
- **Mentions**: User mentions and their information

#### Processing Information
```
Cache Status: ✅ Complete
Media Status: ✅ Processed
Processing Queue: Position #23 (Processed)
Last Processing: January 15, 2024 11:45 AM
Processing Duration: 2.3 seconds
```

#### Categorization
- **Main Category**: Technology
- **Sub-categories**: AI/ML, Natural Language Processing
- **Confidence Scores**: Category assignment confidence levels

### Individual Tweet Actions

#### Update Processing Flags

1. **Access Flag Controls**
   - In the tweet detail modal
   - Click "Update Flags" button

2. **Available Flags**
   ```
   ☐ Cache Complete
   ☐ Media Processed
   ☐ Force Update (Override automatic flags)
   ```

3. **Flag Update Process**
   - Select desired flag states
   - Click "Update Flags"
   - Confirmation appears
   - Tweet status updates in real-time

#### Reprocess Tweet

1. **Reprocessing Options**

   **Pipeline Reprocessing**: Re-runs only the processing pipeline
   ```
   ✓ Faster execution
   ✓ Maintains cached data
   ✓ Updates categorization and metadata
   ```

   **Full Reprocessing**: Complete recache and reprocessing
   ```
   ✓ Fresh data download
   ✓ Re-downloads media files
   ✓ Complete pipeline execution
   ⚠️ Slower execution
   ```

2. **Reprocessing Workflow**
   - Select reprocessing type
   - Choose priority level (Normal/High)
   - Confirm action
   - Tweet enters processing queue
   - Monitor progress via status indicators

## Bulk Operations

### Selecting Tweets

#### Selection Methods

1. **Individual Selection**
   - Click checkbox next to each tweet
   - Selected tweets highlight in blue

2. **Select All on Page**
   - Click header checkbox
   - Selects all visible tweets

3. **Select All Matching Filter**
   - Use "Select All" button when filters are applied
   - Selects all tweets matching current criteria

#### Selection Indicators
```
Selected: 15 tweets
Actions: [Update Flags] [Reprocess] [Clear Selection]
```

### Bulk Operations Modal

Access via "Bulk Operations" button when tweets are selected.

#### Operation Types

##### 1. Update Flags
```
Operation: Update Processing Flags
Selected Tweets: 15
Flags to Update:
☐ Set Cache Complete: True
☐ Set Media Processed: False
☐ Force Update: True

Estimated Time: 5 seconds
```

##### 2. Bulk Reprocessing
```
Operation: Reprocess Tweets
Selected Tweets: 15
Reprocessing Type: 
⚪ Pipeline Only (Recommended)
⚪ Full Reprocessing

Priority: Normal

Estimated Time: 3-5 minutes
Queue Position: Added to end
```

##### 3. Bulk Export
```
Operation: Export Tweet Data
Selected Tweets: 15
Export Format:
⚪ JSON
⚪ CSV
⚪ Excel

Include:
☐ Full Content Data
☐ Processing Metadata
☐ Media Information
```

### Bulk Operation Progress

#### Progress Tracking
```
Bulk Operation: Update Flags
Progress: ████████░░ 80% (12/15 completed)
Estimated Remaining: 30 seconds

Results:
✅ Successful: 12
❌ Failed: 0
⏳ Pending: 3
```

#### Results Summary
```
Bulk Operation Completed
Total Tweets: 15
Successful: 14
Failed: 1

Failed Tweet Details:
- Tweet ID 9876543210987654321: Database connection error
```

## Statistics and Analytics

### Accessing Statistics

Click "View Statistics" button to open the analytics modal.

### Overview Dashboard

#### Tweet Cache Statistics
```
Total Tweets: 15,247
Cache Complete: 12,856 (84.3%)
Cache Incomplete: 2,391 (15.7%)
Average Cache Time: 2.3 seconds
```

#### Media Processing Statistics
```
Total Media Files: 8,432
Processed: 7,891 (93.6%)
Pending: 541 (6.4%)
Average Processing Time: 4.7 seconds
Total Storage: 2.3 GB
```

#### Processing Queue Health
```
Queue Status: ✅ Healthy
Unprocessed: 234 tweets
Average Wait Time: 45 seconds
Throughput: 150 tweets/hour
Last Processing: 2 minutes ago
```

### Performance Metrics

#### Processing Trends
- **Hourly Processing Rate**: Line chart showing tweets processed over time
- **Success Rate**: Processing success percentage over the last 7 days
- **Error Trends**: Common error types and frequencies

#### Category Distribution
```
Technology: 4,832 tweets (31.7%)
Science: 3,247 tweets (21.3%)
Business: 2,891 tweets (19.0%)
Entertainment: 2,156 tweets (14.1%)
Sports: 1,821 tweets (11.9%)
Other: 300 tweets (2.0%)
```

#### Storage and Resource Usage
```
Database Size: 847 MB
Media Storage: 2.3 GB
Average Tweet Size: 56 KB
Cache Hit Rate: 94.7%
```

## Common Workflows

### 1. Finding Incomplete Tweets

**Goal**: Identify and fix tweets that haven't been fully processed.

**Steps**:
1. Use Quick Filter: Set "Cache Complete" to "Incomplete"
2. Sort by "Created Date" (oldest first) to prioritize older tweets
3. Select all incomplete tweets using bulk selection
4. Use "Bulk Reprocessing" with "Pipeline Only" option
5. Monitor progress via statistics dashboard

### 2. Monitoring Recent Activity

**Goal**: Track newly added tweets and their processing status.

**Steps**:
1. Sort by "Created Date" (newest first)
2. Use Advanced Filter: "Recently Updated (Last 24h)"
3. Review status indicators for any processing issues
4. Use individual "Reprocess" for any failed tweets

### 3. Category-Based Management

**Goal**: Manage tweets within specific categories.

**Steps**:
1. Use Category filter to select desired category
2. Review category-specific processing statistics
3. Apply category-specific processing rules
4. Use bulk operations for category-wide updates

### 4. Media Processing Cleanup

**Goal**: Ensure all media files are properly processed.

**Steps**:
1. Filter by "Media Processed: Pending"
2. Check available storage space
3. Prioritize tweets with multiple media files
4. Use bulk reprocessing for media-specific processing
5. Monitor storage usage in statistics

### 5. Performance Optimization

**Goal**: Improve overall system performance.

**Steps**:
1. Review statistics for bottlenecks
2. Identify tweets with long processing times
3. Reprocess failed or stale tweets
4. Monitor queue health and throughput
5. Schedule bulk operations during off-peak hours

## Tips and Best Practices

### Search Optimization

1. **Use Specific Keywords**: More specific searches return more relevant results
2. **Combine Filters**: Use search with filters for precise results
3. **Regular Expressions**: Advanced users can use regex patterns in search
4. **Save Common Searches**: Bookmark frequently used filter combinations

### Performance Tips

1. **Pagination**: Use appropriate page sizes (50-100 tweets) for optimal performance
2. **Bulk Operations**: Process multiple tweets together rather than individually
3. **Off-Peak Processing**: Schedule heavy operations during low-activity periods
4. **Monitor Resources**: Keep an eye on database and storage usage

### Data Management

1. **Regular Cleanup**: Periodically review and clean up failed or duplicate tweets
2. **Backup Before Bulk Operations**: Create backups before major changes
3. **Version Control**: Track changes through the updated timestamp
4. **Category Maintenance**: Regularly review and update category assignments

### Workflow Efficiency

1. **Use Keyboard Shortcuts**: 
   - `Ctrl+A`: Select all tweets on page
   - `Ctrl+F`: Quick search focus
   - `Escape`: Close modals
   - `Enter`: Execute searches

2. **Bookmark Common Views**: Save frequently used filter combinations
3. **Monitor Progress**: Use the statistics dashboard to track processing health
4. **Batch Processing**: Group similar operations for efficiency

## Troubleshooting

### Common Issues

#### Search Not Working
**Symptoms**: Search returns no results or incorrect results
**Solutions**:
1. Clear browser cache and reload page
2. Check for JavaScript errors in browser console
3. Verify database connectivity
4. Try simpler search terms

#### Slow Performance
**Symptoms**: Interface loads slowly or operations timeout
**Solutions**:
1. Reduce page size (use fewer tweets per page)
2. Simplify filters and search criteria
3. Check database performance
4. Clear browser cache
5. Restart the Knowledge Base Agent

#### Processing Stuck
**Symptoms**: Tweets remain in processing state
**Solutions**:
1. Check processing queue health in statistics
2. Restart the background processing service
3. Use individual reprocessing for stuck tweets
4. Check system resources (CPU, memory, disk space)

#### Missing Data
**Symptoms**: Tweets or details not displaying
**Solutions**:
1. Refresh the page
2. Check migration completion status
3. Verify database connectivity
4. Review application logs for errors

### Error Messages

#### "Failed to load tweets"
- **Cause**: Database connection issues or API errors
- **Solution**: Check network connectivity and restart services

#### "Operation failed"
- **Cause**: Insufficient permissions or database constraints
- **Solution**: Check user permissions and database status

#### "Invalid search criteria"
- **Cause**: Malformed search query or unsupported characters
- **Solution**: Simplify search terms and avoid special characters

### Getting Help

1. **Application Logs**: Check `/logs/` directory for detailed error information
2. **Browser Console**: Open developer tools to check for JavaScript errors
3. **Database Logs**: Review PostgreSQL logs for database-related issues
4. **System Resources**: Monitor CPU, memory, and disk usage
5. **Documentation**: Refer to the implementation guide for technical details

### Emergency Procedures

#### System Unresponsive
1. Stop the Knowledge Base Agent service
2. Check system resources and free up space if needed
3. Restart PostgreSQL database service
4. Restart the Knowledge Base Agent
5. Verify basic functionality before resuming operations

#### Data Corruption Suspected
1. Stop all processing immediately
2. Create emergency backup using backup CLI tool
3. Run database integrity checks
4. Contact system administrator
5. Consider restoring from last known good backup

---

**User Guide Status**: ✅ Complete - All features documented with examples
**Next Steps**: User training and feedback collection 