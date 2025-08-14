# Steering Documents

This directory contains steering documents that provide guidance and standards for the AI Agent Rebuild project. These documents are automatically included in AI assistant context to ensure consistent implementation patterns.

## Document Overview

### Core Architecture Documents

#### [backend-architecture.md](./backend-architecture.md)
**Purpose**: Defines the overall backend architecture patterns and implementation guidelines.

**Key Topics**:
- Seven-phase pipeline architecture for Twitter/X bookmark processing
- Database-driven knowledge base management without flat file dependencies
- Sub-phase intelligence with bookmark caching, media analysis, content understanding, and AI categorization
- Command-line testable architecture for all phases and sub-phases
- Service layer patterns with dependency injection
- Repository patterns for data access
- Model layer with Twitter/X-specific fields and provenance tracking

**Updated for**: Twitter/X-focused seven-phase pipeline with intelligent sub-phase processing

#### [ai-integration-patterns.md](./ai-integration-patterns.md)
**Purpose**: Provides patterns for integrating AI capabilities throughout the system.

**Key Topics**:
- Seven-phase AI processing pipeline with model routing
- Twitter/X-specific AI processing (thread detection, media analysis)
- XML-based prompting system for consistent AI interactions
- Phase-specific model selection (vision, kb_generation, synthesis, chat, embeddings)
- Provenance tracking for AI model usage across all phases
- Performance optimization and caching strategies

**Updated for**: Seven-phase pipeline with Twitter/X thread processing and XML prompting

#### [seven-phase-pipeline.md](./seven-phase-pipeline.md)
**Purpose**: Comprehensive guide to the seven-phase Twitter/X bookmark processing pipeline.

**Key Topics**:
- Detailed implementation patterns for all seven phases
- Sub-phase processing logic (2.1, 3.1, 3.2, 3.3)
- Intelligent processing logic to avoid unnecessary reprocessing
- Dependency validation and error recovery
- Command-line testing support
- Real-time progress tracking and WebSocket updates

**New Document**: Created specifically for the seven-phase architecture

#### [twitter-x-integration.md](./twitter-x-integration.md)
**Purpose**: Specialized patterns for Twitter/X API integration and content processing.

**Key Topics**:
- Twitter/X API authentication and rate limiting
- Bookmark fetching from API and export files
- Thread detection and processing algorithms
- Media caching and storage patterns
- Engagement metrics tracking and analytics
- Database schema patterns for Twitter/X-specific fields

**New Document**: Created for Twitter/X-specific integration patterns

### API and Interface Standards

#### [api-design-standards.md](./api-design-standards.md)
**Purpose**: Standards for designing REST APIs in the system.

**Key Topics**:
- Twitter/X-specific API endpoints and response schemas
- Seven-phase pipeline API patterns
- Sub-phase management endpoints
- Command-line testing support endpoints
- Authentication and authorization patterns
- Real-time features with WebSocket integration

**Updated for**: Twitter/X-specific endpoints and pipeline control APIs

### Quality and Security Standards

#### [testing-standards.md](./testing-standards.md)
**Purpose**: Comprehensive testing standards and practices.

**Key Topics**:
- Twitter/X content API testing patterns
- Seven-phase pipeline integration testing
- Command-line testing integration
- Model router testing for all phases
- Sub-phase processing validation
- Error recovery and rollback testing

**Updated for**: Twitter/X-focused testing with pipeline-specific test patterns

#### [security-guidelines.md](./security-guidelines.md)
**Purpose**: Security guidelines and best practices.

**Key Topics**:
- Authentication and authorization patterns
- Input validation and sanitization
- Data protection and privacy
- Security monitoring and audit logging
- Model configuration security
- Twitter/X API security considerations

**Status**: Existing document - no major updates needed for Twitter/X focus

## Implementation Guidance

### How Steering Documents Work

1. **Automatic Inclusion**: These documents are automatically included in AI assistant context when working on the project
2. **Implementation Patterns**: Provide concrete code examples and patterns to follow
3. **Consistency**: Ensure consistent implementation across all components
4. **Best Practices**: Encode team knowledge and best practices into reusable guidance

### Key Architectural Decisions Reflected

#### Seven-Phase Pipeline Architecture
- **Phase 1**: Initialization and system setup
- **Phase 2**: Bookmark fetching with sub-phase 2.1 (bookmark caching)
- **Phase 3**: Content processing with three sub-phases (3.1 media analysis, 3.2 content understanding, 3.3 categorization)
- **Phase 4**: Synthesis generation
- **Phase 5**: Embedding generation
- **Phase 6**: README generation
- **Phase 7**: Git sync

#### Twitter/X-First Design
- Specialized for Twitter/X bookmark processing
- Thread detection and collective understanding
- Media analysis with vision models
- Engagement metrics tracking
- Author and tweet metadata management

#### Database-Driven Knowledge Base
- No flat file dependencies
- All content stored in unified database schema
- Dynamic generation of knowledge base items
- Temporary file generation only for Git operations

#### Command-Line Testable
- Full CLI testing capabilities for all phases
- Independent phase and sub-phase execution
- Status checking and progress monitoring
- Error recovery and rollback testing

#### Intelligent Processing Logic
- Avoid unnecessary reprocessing of unchanged content
- Dependency validation between phases
- Sub-phase completion tracking
- Incremental processing support

### Usage Guidelines

1. **Read Before Implementation**: Review relevant steering documents before implementing new features
2. **Follow Patterns**: Use the provided code patterns and examples as templates
3. **Update When Needed**: Update steering documents when architectural decisions change
4. **Consistency Check**: Ensure new implementations align with existing patterns

### Document Maintenance

- **Regular Review**: Steering documents should be reviewed and updated as the project evolves
- **Version Control**: All changes to steering documents should be tracked in version control
- **Team Alignment**: Ensure all team members are familiar with the current steering documents
- **Pattern Evolution**: Update patterns based on lessons learned during implementation

## Quick Reference

### For Backend Development
- Start with [backend-architecture.md](./backend-architecture.md) for overall patterns
- Use [seven-phase-pipeline.md](./seven-phase-pipeline.md) for pipeline implementation
- Reference [twitter-x-integration.md](./twitter-x-integration.md) for Twitter/X-specific features

### For AI Integration
- Follow [ai-integration-patterns.md](./ai-integration-patterns.md) for AI service integration
- Use XML prompting patterns for consistent AI interactions
- Implement proper model routing and provenance tracking

### For API Development
- Follow [api-design-standards.md](./api-design-standards.md) for REST API patterns
- Implement Twitter/X-specific endpoints as specified
- Support command-line testing endpoints

### For Testing
- Use [testing-standards.md](./testing-standards.md) for comprehensive testing patterns
- Implement pipeline-specific integration tests
- Support command-line testing scenarios

This steering document system ensures consistent, high-quality implementation across the entire AI Agent Rebuild project while maintaining focus on the Twitter/X-centric seven-phase pipeline architecture.