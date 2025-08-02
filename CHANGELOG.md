# Changelog

All notable changes to the earnings-analyzer package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-01-XX

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