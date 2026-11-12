# Unitalk model provider for Hermes

Connect Hermes to the Unitalk LiteLLM gateway at
`https://llmgateway.unitalk.ai/v1`. The provider uses the OpenAI-compatible
Chat Completions API and discovers available models from the gateway.

## Install

Copy `__init__.py` and `plugin.yaml` into the active Hermes profile's
`$HERMES_HOME/plugins/model-providers/unitalk/` directory. For the default
profile, `$HERMES_HOME` is normally `~/.hermes`. Install separately for each
profile that should use the provider.

For example, from this plugin's directory:

```sh
mkdir -p "${HERMES_HOME:-$HOME/.hermes}/plugins/model-providers/unitalk"
cp __init__.py plugin.yaml "${HERMES_HOME:-$HOME/.hermes}/plugins/model-providers/unitalk/"
```

Set `UNITALK_API_KEY` in that profile's `.env` or in the environment. If it
is unset, Hermes can use `OPENAI_API_KEY` instead. The key must be accepted by
the Unitalk gateway, even when it comes from `OPENAI_API_KEY`. Do not commit
credentials. Explicit Hermes credential and pool settings can take precedence.

Run `hermes model` and select **Unitalk**, then choose a model offered by the
gateway. Alternatively, configure `model.provider` as `unitalk` and set
`model.default` to a model ID from the gateway. A failed or unauthorized
model-list request cannot populate the picker; verify your key and access.

The plugin adds no model capability claims or fallback models: the available
model IDs and their support for tools, vision, or streaming depend on the
gateway's configuration.
