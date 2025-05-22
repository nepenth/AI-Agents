# Using Reasoning Models in Knowledge Base Agent

This guide explains how to enable and use reasoning capabilities with models like Cogito in the Knowledge Base Agent.

## Overview

The Knowledge Base Agent now supports models with reasoning capabilities, which allows it to perform more thoughtful step-by-step analysis during various generation tasks. This capability has been integrated into:

- AI Categorization for tweet content
- KB Item Generation
- README Generation

## Configuration

To enable reasoning mode, add or modify the following variables in your `.env` file:

```
TEXT_MODEL="cogito"                # Set to a model that supports reasoning, like Cogito
TEXT_MODEL_THINKING=true           # Enable reasoning capabilities
```

When `TEXT_MODEL_THINKING` is set to `true`, the agent will use the Ollama chat API instead of the generate API, with a special system prompt that enables reasoning.

## How it Works

When reasoning mode is enabled:

1. For each LLM task, the agent creates a message array with:
   - A system message that enables the thinking subroutine
   - A user message with the specific task prompt
   - (For retry attempts) Additional messages with feedback on previous failures

2. The agent uses the `ollama_chat` endpoint instead of `ollama_generate`, which supports the message-based format required for reasoning.

3. Special prompts have been created for each task type that encourage the model to think step-by-step before providing a response.

## Benefits

Using reasoning models provides several benefits:

- **Improved categorization**: Better identification of technical categories by thinking through the content more thoroughly
- **Higher quality KB items**: More comprehensive and well-structured knowledge base content
- **Better error recovery**: When a response fails validation, the agent can provide feedback to the model for the next attempt
- **Conversational context**: The chat format allows maintaining context through retry attempts

## Example Usage with Ollama

To run Cogito with Ollama locally:

```bash
# Pull the model
ollama pull cogito

# Start the Ollama server
ollama serve

# In a separate terminal, test the model with reasoning
curl http://localhost:11434/api/chat -d '{
  "model": "cogito",
  "messages": [
    {
      "role": "system",
      "content": "Enable deep thinking subroutine."
    },
    {
      "role": "user",
      "content": "How would you categorize a technical article about circuit breaker patterns in microservices?"
    }
  ]
}'
```

## Fallback Behavior

If the reasoning-capable model fails, the agent will still attempt to use the fallback model configured in `FALLBACK_MODEL`. It will maintain the reasoning mode if enabled, using the same chat-based API for the fallback model.

## Implementation Details

The reasoning support is implemented across several components:

- `config.py`: Added a new `text_model_thinking` boolean setting
- `http_client.py`: Added an `ollama_chat` method to support chat API
- `prompts.py`: Added a new `ReasoningPrompts` class with specialized prompts
- `ai_categorization.py`: Updated to use chat format when reasoning is enabled
- `kb_item_generator.py`: Updated to use reasoning for content generation
- `readme_generator.py`: Updated to use reasoning for README content

## Compatibility

This feature maintains backward compatibility with existing models. When `TEXT_MODEL_THINKING=false` or the variable is not set, the agent will continue to use the standard generate API with the existing prompts. 