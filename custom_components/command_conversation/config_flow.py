"""Config flow for the Command Conversation integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COMMAND,
    CONF_ERROR_MESSAGE,
    CONF_LANGUAGES,
    CONF_TIMEOUT,
    DEFAULT_ERROR_MESSAGE,
    DEFAULT_LANGUAGES,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

COMMAND_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
)
TIMEOUT_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=1, max=600, step=1, mode=NumberSelectorMode.BOX)
)


def _schema(defaults: dict[str, Any], *, include_name: bool) -> vol.Schema:
    """Build the form schema, prefilled with the given defaults."""
    fields: dict[Any, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME))] = str
    fields[vol.Required(CONF_COMMAND, default=defaults.get(CONF_COMMAND, ""))] = (
        COMMAND_SELECTOR
    )
    fields[
        vol.Required(CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
    ] = TIMEOUT_SELECTOR
    fields[
        vol.Optional(
            CONF_LANGUAGES, default=defaults.get(CONF_LANGUAGES, DEFAULT_LANGUAGES)
        )
    ] = str
    fields[
        vol.Required(
            CONF_ERROR_MESSAGE,
            default=defaults.get(CONF_ERROR_MESSAGE, DEFAULT_ERROR_MESSAGE),
        )
    ] = str
    return vol.Schema(fields)


class CommandConversationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the command to run."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_COMMAND].strip():
                errors[CONF_COMMAND] = "empty_command"
            else:
                user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}, include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Allow editing the command after setup."""
        return CommandConversationOptionsFlow()


class CommandConversationOptionsFlow(OptionsFlow):
    """Edit the command, timeout and error message without re-adding."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_COMMAND].strip():
                errors[CONF_COMMAND] = "empty_command"
            else:
                user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])
                return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current, include_name=False),
            errors=errors,
        )
