import datetime
import discord
import requests
import state

from bs4 import BeautifulSoup

def _get_embed_content_url(url: str) -> str:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    def is_embed_image(meta):
        return meta.get("property") == "og:image"

    meta = soup.find(is_embed_image)

    if meta:
        return meta.get("content")

    return None

async def _get_message_author(guild_id: int, message: discord.Message) -> str:
    if isinstance(message.author, discord.Member):
        config = await state.get_config(guild_id)

        if any(role.name == config.discord_developer_role for role in message.author.roles):
            return message.author.name + " (Developer)"

    return message.author.name

def _get_message_images(message: discord.Message, cur_num_images: int, max_images: int) -> list[str]:
    image_urls = []

    for attachment in message.attachments:
        if cur_num_images >= max_images:
            break

        if attachment.content_type.startswith("image"):
            image_urls.append(attachment.url)
            cur_num_images += 1

    for embed in message.embeds:
        if cur_num_images >= max_images:
            break

        if embed.type == "image":
            embed_content_url = _get_embed_content_url(embed.url)
            if embed_content_url:
                image_urls.append(embed_content_url)
                cur_num_images += 1

    return image_urls

async def _get_image_description_for_message(guild_id: int, message: discord.Message, image_urls: list[str]) -> str:
    if not image_urls:
        return message.content

    message_context = await get_history(guild_id, message, 5, 0)
    analysis_suite = await state.get_analysis_suite(guild_id)

    image_analysis = await analysis_suite.analyse_images(message_context, image_urls)

    return f"\n<IMAGES ATTACHED TO THIS MESSAGE: {image_analysis}>"

async def get_history(guild_id: int, message: discord.Message, limit: int, max_images: int) -> str:
    combined_history = ""
    image_urls = []
    image_count = 0

    after = message.created_at - datetime.timedelta(seconds=3)
    message_history = [history_message async for history_message in message.channel.history(limit=limit, after=after)]

    for history_message in message_history:
        message_content = history_message.content

        if history_message.author.name == message.author.name and image_count < max_images:
            new_image_urls = _get_message_images(history_message, image_count, max_images)
            if new_image_urls:
                image_urls += new_image_urls
                image_count += len(new_image_urls)
                message_content += await _get_image_description_for_message(guild_id, history_message, new_image_urls)

        if history_message.type == discord.MessageType.reply:
            msg_ref_id       = history_message.reference.message_id
            msg_ref          = await history_message.channel.fetch_message(msg_ref_id)
            message_content += f"\n<REPLYING TO: {await _get_message_author(guild_id, msg_ref)}: {msg_ref.content}>"

        combined_history += f"\t{await _get_message_author(guild_id, history_message)}: {message_content}\n\n"

    return combined_history