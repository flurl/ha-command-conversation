"""Constants for the Command Conversation integration."""

DOMAIN = "command_conversation"

CONF_COMMAND = "command"
CONF_TIMEOUT = "timeout"
CONF_ERROR_MESSAGE = "error_message"
CONF_LANGUAGES = "languages"

DEFAULT_NAME = "Command Conversation"
DEFAULT_TIMEOUT = 60
# Empty means "any language" (MATCH_ALL). Prefer naming the language explicitly:
# a MATCH_ALL agent makes the pipeline use the STT language for local intent
# matching, and an ambiguous variant like de-AT then resolves non-deterministically
# (it can land on de-CH).
DEFAULT_LANGUAGES = ""
DEFAULT_ERROR_MESSAGE = "Entschuldigung, der Assistent hat nicht geantwortet."

# Maximum bytes of stdout accepted as an answer, to stop a runaway command
# from feeding a novel into TTS.
MAX_OUTPUT_BYTES = 16000
