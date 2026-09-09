"""Conversation entity that pipes text through an arbitrary command."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_COMMAND,
    CONF_ERROR_MESSAGE,
    CONF_LANGUAGES,
    CONF_TIMEOUT,
    DEFAULT_ERROR_MESSAGE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_OUTPUT_BYTES,
)

_LOGGER = logging.getLogger(__name__)


class CommandError(Exception):
    """The configured command did not produce a usable answer."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    async_add_entities([CommandConversationEntity(config_entry)])


class CommandConversationEntity(conversation.ConversationEntity):
    """Conversation agent backed by a local command.

    Deliberately does NOT declare ConversationEntityFeature.CONTROL: the command
    gets the transcript and nothing else, and cannot reach the Assist API. That
    also keeps Home Assistant's full local intent set in play when the pipeline
    has "prefer handling commands locally" enabled.
    """

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Command Conversation",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Languages this agent claims to support.

        Naming a language matters beyond documentation: when an agent reports
        MATCH_ALL the pipeline feeds the STT language into local intent matching
        instead of the pipeline language. An ambiguous variant such as "de-AT"
        then resolves non-deterministically between "de" and "de-CH", because
        DefaultAgent._load_intents passes a set to language_util.matches and the
        tie is broken by set ordering. Naming "de" here keeps it deterministic.
        """
        configured = str(self._option(CONF_LANGUAGES, "") or "").strip()
        if not configured:
            return MATCH_ALL
        return [lang.strip() for lang in configured.split(",") if lang.strip()]

    def _option(self, key: str, default: Any = None) -> Any:
        """Read a setting, preferring options (editable) over data (initial)."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Run the command and speak its stdout."""
        with async_get_chat_session(self.hass, user_input.conversation_id) as session:
            response = intent.IntentResponse(language=user_input.language)
            try:
                answer = await self._async_run_command(user_input, session.conversation_id)
            except CommandError as err:
                _LOGGER.error("%s: %s", self.entry.title, err)
                response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    self._option(CONF_ERROR_MESSAGE, DEFAULT_ERROR_MESSAGE),
                )
            else:
                response.async_set_speech(answer)

            return conversation.ConversationResult(
                response=response,
                conversation_id=session.conversation_id,
                continue_conversation=False,
            )

    async def _async_run_command(
        self,
        user_input: conversation.ConversationInput,
        conversation_id: str,
    ) -> str:
        """Pipe the transcript into the command and return its stdout."""
        command: str = self._option(CONF_COMMAND)
        timeout: int = self._option(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        # Context is passed as environment variables rather than substituted into
        # the command string: spoken text must never be interpolated into a shell
        # command line.
        env = {
            **os.environ,
            "HA_CONVERSATION_ID": conversation_id or "",
            "HA_DEVICE_ID": user_input.device_id or "",
            "HA_SATELLITE_ID": user_input.satellite_id or "",
            "HA_LANGUAGE": user_input.language or "",
            "HA_AGENT_ID": user_input.agent_id or "",
        }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as err:
            raise CommandError(f"could not start command: {err}") from err

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(user_input.text.encode("utf-8")), timeout
            )
        except TimeoutError as err:
            proc.kill()
            await proc.wait()
            raise CommandError(f"command timed out after {timeout}s") from err

        if proc.returncode != 0:
            raise CommandError(
                f"command exited {proc.returncode}: "
                f"{stderr.decode('utf-8', 'replace').strip()[:500]}"
            )

        if len(stdout) > MAX_OUTPUT_BYTES:
            _LOGGER.warning(
                "%s: truncating %d bytes of output to %d",
                self.entry.title,
                len(stdout),
                MAX_OUTPUT_BYTES,
            )
            stdout = stdout[:MAX_OUTPUT_BYTES]

        answer = stdout.decode("utf-8", "replace").strip()
        if not answer:
            raise CommandError(
                "command produced no output on stdout "
                f"(stderr: {stderr.decode('utf-8', 'replace').strip()[:500]})"
            )

        return answer
