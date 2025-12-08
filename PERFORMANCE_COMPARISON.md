# System Performance Comparison: MacBook vs Desktop

**Date:** December 8, 2025
**Purpose:** Compare processing performance between MacBook and desktop systems for job analytics pipeline execution

## Executive Summary

This document compares the processing capabilities of two development systems used for the job analytics platform. The MacBook serves as the primary development environment, while the desktop provides additional processing capacity for intensive workloads.

## System Specifications

### MacBook (Primary Development Machine)
- **OS:** macOS 15.6.1 (Darwin 24.6.0)
- **Processor:** Intel Core i5 (4 cores, 8 threads with hyper-threading)
- **Memory:** 16 GB LPDDR4X (3733 MHz)
- **Storage:** 466 GB SSD (403 GB available, 10 GB used)
- **Python Version:** 3.9.6

### Desktop (Secondary Machine)
- **OS:** [TBD - Windows/Linux]
- **Processor:** [TBD - CPU specs]
- **Memory:** [TBD - RAM amount and type]
- **Storage:** [TBD - Storage capacity and type]
- **Python Version:** [TBD]

## Performance Benchmarks

### CPU Performance
- **MacBook:** 1.53 seconds (10M mathematical iterations)
- **Desktop:** [TBD]

### Memory Performance
- **MacBook:** 16 GB total, efficient LPDDR4X memory
- **Desktop:** [TBD]

### Job Analytics Pipeline Performance

#### Current Pipeline Characteristics
Based on recent production runs (2025-12-04 data):
- **Total jobs processed:** 1,654 raw jobs
- **Classification rate:** 58.1% (961 jobs enriched)
- **API cost:** $9.38 total ($0.00976 per classified job)
- **Token usage:** ~9,293 tokens per classification

#### Parallel Processing Capability
- **MacBook:** 8 CPU threads available (4 cores + hyper-threading)
- **Concurrent processes:** Limited by memory (16 GB total)
- **Network:** Standard broadband connection
- **Desktop:** [TBD - CPU threads, memory constraints]

## Pipeline Execution Scenarios

### Scenario 1: Single City Processing
- **Adzuna only:** ~50-100 jobs, 5-15 minutes
- **Greenhouse only:** ~100-200 jobs, 15-30 minutes
- **Dual source:** ~150-300 jobs, 20-45 minutes

### Scenario 2: Multi-City Parallel Processing
- **All 3 cities simultaneously:** High memory usage, potential rate limiting
- **MacBook capacity:** Can handle 2-3 concurrent processes reliably
- **Desktop capacity:** [TBD]

### Scenario 3: Large-Scale Data Processing
- **Memory intensive:** Classification requires holding job data in memory
- **Current limit:** ~3,000-4,000 jobs per run before memory constraints
- **Optimization:** Incremental processing reduces memory footprint

## Performance Recommendations

### For MacBook (Current Setup)
✅ **Strengths:**
- Sufficient for development and small-scale testing
- Good for single-city pipeline runs
- Adequate for API testing and validation

⚠️ **Limitations:**
- Memory constraints for large parallel runs
- CPU bottleneck for computationally intensive tasks
- Network-dependent for API calls

### For Desktop (Recommended for Heavy Processing)
[TBD based on specs]

### Optimization Strategies

1. **Parallel Execution Guidelines:**
   - MacBook: Max 2 cities simultaneously
   - Desktop: [TBD]
   - Rate limiting: Monitor Anthropic API limits (429 errors)

2. **Memory Management:**
   - Use incremental processing for large datasets
   - Implement data streaming where possible
   - Monitor memory usage during long runs

3. **Cost Optimization:**
   - Current cost: $0.00976 per classified job
   - Target: Reduce through prompt caching and batching
   - Monitor API usage patterns

## Development Workflow Recommendations

### Daily Development (MacBook)
- Unit testing and validation
- Small-scale pipeline testing
- Code development and debugging

### Production Processing (Desktop)
- Large-scale data ingestion
- Parallel multi-city processing
- Performance benchmarking

### Hybrid Approach
- Develop on MacBook, deploy to desktop for heavy processing
- Use desktop for batch processing during off-hours
- Sync results between systems

## Monitoring and Metrics

### Key Performance Indicators
1. **Processing time per job:** Target < 10 seconds
2. **Memory usage:** Keep under 80% capacity
3. **API rate limits:** Monitor 429 error frequency
4. **Classification accuracy:** Maintain > 90% accuracy

### Tools for Monitoring
- Pipeline status checker: `python wrapper/check_pipeline_status.py`
- Cost tracking: Anthropic dashboard integration
- System monitoring: Built-in OS tools + Python profiling

## Future Considerations

### Hardware Upgrades
- **MacBook:** Consider upgrading to M3/M4 chip for better performance
- **Desktop:** [TBD based on current specs]

### Software Optimizations
- Implement prompt caching (potential 50-90% cost reduction)
- Batch classification requests
- Optimize database queries and indexing

### Cloud Processing
- Consider AWS/GCP instances for very large-scale processing
- Use spot instances for cost-effective batch processing
- Implement hybrid cloud-local processing pipeline

---

*To update this document with desktop specifications, run performance benchmarks on the desktop system and update the [TBD] sections accordingly.*
