# Changelog

All notable changes to the earnings-analyzer package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2] - 2025-08-02

### Fixed
- **Database Error Handling**: Comprehensive error handling for all database operations with proper rollback and connection cleanup
- **Input Validation**: Added robust input validation across all modules preventing invalid ticker symbols, quarters, years, and API parameters
- **Network Reliability**: Implemented retry logic with exponential backoff for all API requests (FMP, Gemini, web scraping)
- **Memory Management**: Added automatic transcript truncation for very large texts and proper resource cleanup
- **Rate Limiting**: Intelligent rate limiting for both Gemini API (15 requests/minute) and FMP API with automatic backoff
- **Connection Resilience**: Database connections now automatically reconnect when lost and include proper cleanup on exit
- **Security Enhancements**: API keys redacted from logs, SQL injection prevention, input sanitization
- **Batch Processing Interface**: Fixed data structure mismatch between `batch_fetch_transcripts()` and `batch_score_sentiment()`

### Added
- **Enhanced API Functions**: New convenience functions `batch_analyze_earnings_calls()`, `quick_sentiment_analysis()`, `check_data_availability()`, `validate_api_configuration()`
- **Better Error Messages**: Specific, actionable error messages with step-by-step logging for complex operations
- **User Agent Rotation**: Randomized headers and user agents for web scraping to avoid detection
- **Configuration Validation**: Built-in tools to check API keys and dependencies before analysis
- **Progress Tracking**: Clear progress indicators for multi-step analysis operations
- **Graceful Degradation**: Analysis continues even if optional components (like stock performance) fail

### Changed
- **README Documentation**: Updated batch processing examples to show correct data structure handling
- **Error Logging**: Consistent error logging patterns across all modules with appropriate detail levels
- **Input Sanitization**: All ticker symbols normalized to uppercase, comprehensive date format handling
- **API Request Handling**: Centralized request handling with proper timeout, retry, and error recovery
- **Database Schema**: Enhanced database operations with better duplicate handling and data integrity

### Technical Improvements
- **Type Safety**: Added comprehensive type hints throughout the codebase
- **Resource Management**: Context manager support for `EarningsAnalyzer` class and automatic cleanup
- **Performance Optimization**: Efficient batch processing with smart delays and connection reuse
- **Robustness**: Enhanced error boundaries preventing single component failures from breaking entire analysis
- **Security**: Input validation preventing malicious data injection and API key exposure


## [1.2.0] - 2025-08-02

### Added
- **Custom Prompt Analysis**: Define specialized research questions with custom AI prompts for sentiment analysis
- New `custom_prompt` parameter for `score_sentiment()`, `batch_score_sentiment()`, `analyze_earnings_call()`, `quick_sentiment_analysis()`, and all `EarningsAnalyzer` methods
- Support for custom JSON response structures from Gemini API based on user-defined prompts
- Enhanced function signatures across all analysis methods for consistency

### Changed
- **Updated default model**: Changed from `gemini-1.5-flash` to `gemini-2.5-flash` for improved performance
- **Architecture refactoring**: Eliminated duplicate function definitions across modules
- **Import hierarchy**: Established clean separation between composable functions and orchestrator classes
- Custom prompt analyses are not cached in database due to unpredictable response structures
- Enhanced error handling and logging throughout the package

### Fixed
- **Namespace collisions**: Resolved duplicate function names that caused import conflicts
- **Circular import issues**: Fixed improper dependency relationships between modules
- **Function consistency**: Ensured all sentiment analysis functions accept the same parameters
- Database caching logic now properly handles both default and custom prompt scenarios

### Technical Improvements
- Single source of truth for all composable functions
- Clear module ownership and responsibilities
- Improved documentation with working examples
- Enhanced backward compatibility for existing user code

## [1.0.2] - Previous Release

### Initial Features
- Basic sentiment analysis of earnings call transcripts
- Company profile and stock performance analysis
- Database persistence and caching
- Command line interface
- Composable function architecture