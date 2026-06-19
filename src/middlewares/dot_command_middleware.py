from aiogram import BaseMiddleware, types


class DotCommandMiddleware(BaseMiddleware):
    """
    Rewrites messages starting with '.' to use '/' so that dot-prefixed
    commands (e.g. .ping, .daily, .solved 1 4) are treated identically
    to their slash equivalents by all downstream handlers.
    """

    async def __call__(self, handler, event, data):
        if (
            isinstance(event, types.Message)
            and event.text
            and event.text.startswith(".")
            and len(event.text) > 1
            and not event.text.startswith("..")  # ignore ellipsis / double-dot
        ):
            # Rewrite text: ".cmd args" → "/cmd args"
            new_text = "/" + event.text[1:]

            # Extract command length for the entity (e.g. "/ping" -> length 5)
            first_word = new_text.split()[0]
            cmd_len = len(first_word)
            command_entity = types.MessageEntity(
                type="bot_command",
                offset=0,
                length=cmd_len
            )

            # Ensure the bot_command entity is present at offset 0
            if event.entities is None:
                new_entities = [command_entity]
            else:
                new_entities = list(event.entities)
                has_cmd_entity = any(
                    e.type == "bot_command" and e.offset == 0
                    for e in new_entities
                )
                if not has_cmd_entity:
                    new_entities.insert(0, command_entity)

            # Create a copied event with modified text and entities
            event = event.model_copy(update={
                "text": new_text,
                "entities": new_entities
            })

        return await handler(event, data)
