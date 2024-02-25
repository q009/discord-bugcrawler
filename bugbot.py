import asyncio
import chatproc
import common
import discord
import gpt
import logging
import os
import re
import state
import storage
import time

from discord import app_commands
from dotenv import load_dotenv
from github import Auth
from github import Github
from github import GithubIntegration
from storage import Config
from typing import Optional

# Logging

DIR_LOGS = "logs"
LOG_PATH = f"{DIR_LOGS}/{time.strftime('%Y%m%d-%H%M%S')}.log"

os.makedirs(DIR_LOGS, exist_ok = True)

log_file_handler = logging.FileHandler(LOG_PATH, mode = "w", encoding = "utf-8")
log_file_handler.setLevel(logging.DEBUG)
log_file_handler.setFormatter(logging.Formatter(common.LOG_FORMAT))

log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(logging.INFO)
log_console_handler.setFormatter(logging.Formatter(common.LOG_FORMAT))

_logger = logging.getLogger()
_logger.setLevel(logging.DEBUG)
_logger.addHandler(log_file_handler)
_logger.addHandler(log_console_handler)

load_dotenv()
gpt.init(os.getenv('OPENAI_API_KEY'))
storage.init(os.getenv('MONGO_URI'))

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = MyClient(intents=intents)

async def gh_open(guild_id: int = 0, repo: str = "") -> Github:
    gh_key = ""

    with open(f"certs/{os.getenv('GITHUB_APP_KEY')}", "r") as file:
        gh_key = file.read()

    gh_auth = Auth.AppAuth(os.getenv('GITHUB_APP_ID'), gh_key)
    gh_integration = GithubIntegration(auth=gh_auth)

    if guild_id:
        config = await state.get_config(guild_id)
        repo = config.github_repo.split("/")
    else:
        repo = repo.split("/")

    gh_installation = gh_integration.get_repo_installation(repo[0], repo[1])
    return gh_installation.get_github_for_installation()

async def file_issue(guild_id: int, issue_title: str, issue_md: str) -> str:
    config = await state.get_config(guild_id)

    gh = await gh_open(guild_id=guild_id)
    repo = gh.get_repo(config.github_repo)

    new_issue = repo.create_issue(title=issue_title, body=issue_md, labels=["bug"])

    gh.close()

    return new_issue.html_url

async def verify_config(guild_id: int, config: Config = None) -> str:
    if config.github_repo == "":
        return "github_repo"

    try:
        gh = await gh_open(repo=config.github_repo)
    except Exception as e:
        _logger.error(f"Error opening GitHub: {e}")
        return "github_repo"

    repo_name = gh.get_repo(config.github_repo).full_name

    if repo_name != config.github_repo:
        return "github_repo"

    if config.product_name == "":
        return "product_name"

    if config.product_type == "":
        return "product_type"

    if not config.issue_categories:
        return "issue_categories"

    if config.discord_developer_role == "":
        return "discord_developer_role"

    return None

async def check_config(interaction: discord.Interaction, config: Config) -> bool:
    config_error = await verify_config(interaction.guild.id, config)

    if config_error:
        await interaction.response.send_message(f"Configuration error: {config.get_pretty_name(config_error)}",
                                                ephemeral=True)
        return False

    return True

class Setup(discord.ui.Modal, title="Setup"):
    def __init__(self) -> None:
        super().__init__()

        self.submitted        = False
        self.config           = None
        self.repo             = None
        self.product          = None
        self.issue_categories = None
        self.issue_extra_info = None
        self.developer_role   = None

    async def populate(self, guild_id: int) -> None:
        self.config = state.get_config(guild_id)

        self.repo = discord.ui.TextInput(label=self.config.get_pretty_name("github_repo"),
                                         style=discord.TextStyle.short,
                                         placeholder="user/repo",
                                         required=True)

        self.product = discord.ui.TextInput(label=self.config.get_pretty_name("product_name") + " and " +
                                            self.config.get_pretty_name("product_type"),
                                            placeholder="Product Name\nProduct Type",
                                            style=discord.TextStyle.long,
                                            required=True)

        self.issue_categories = discord.ui.TextInput(label=self.config.get_pretty_name("issue_categories"),
                                                     placeholder="Category 1\nCategory 2\nCategory 3\n...",
                                                     style=discord.TextStyle.paragraph,
                                                     required=True)

        self.issue_extra_info = discord.ui.TextInput(label=self.config.get_pretty_name("issue_extra_info"),
                                                     placeholder="Info to collect 1\nInfo to collect 2\n...",
                                                     style=discord.TextStyle.paragraph,
                                                     required=True)

        self.developer_role = discord.ui.TextInput(label=self.config.get_pretty_name("discord_developer_role"),
                                                   style=discord.TextStyle.short,
                                                   required=True)

        self.repo.default             = self.config.github_repo
        self.product.default          = self.config.product_name + "\n" + self.config.product_type
        self.issue_categories.default = "\n".join(self.config.issue_categories)
        self.issue_extra_info.default = "\n".join(self.config.issue_extra_info)

        self.add_item(self.repo)
        self.add_item(self.product)
        self.add_item(self.issue_categories)
        self.add_item(self.issue_extra_info)
        self.add_item(self.developer_role)

    async def on_submit(self, interaction: discord.Interaction):
        name_type = self.product.value.split("\n")

        # TODO: strip() and remove empty lines
        self.config.github_repo            = self.repo.value
        self.config.product_name           = name_type[0]
        self.config.product_type           = name_type[1] if len(name_type) > 1 else ""
        self.config.issue_categories       = self.issue_categories.value.split("\n")
        self.config.issue_extra_info       = self.issue_extra_info.value.split("\n")
        self.config.discord_developer_role = self.developer_role.value

        self.submitted = True

        if await check_config(interaction, self.config):
            state.set_config(interaction.guild.id, self.config)
            await interaction.response.send_message(f"Setup complete", ephemeral=True)

class BugCorrect(discord.ui.Modal, title="Correct bug report"):
    comment = discord.ui.TextInput(label="Comment",
                                   style=discord.TextStyle.long,
                                   placeholder="",
                                   max_length=400,
                                   required=False)

    submitted = False

    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True
        await interaction.response.send_message(f"Preparing bug report...", ephemeral=True)

class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.comment = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "confirm"
        self.stop()

    @discord.ui.button(label='Regenerate', style=discord.ButtonStyle.blurple)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "regenerate"
        self.stop()

    @discord.ui.button(label='Correct', style=discord.ButtonStyle.blurple)
    async def correct(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "correct"
        correct_modal = BugCorrect()
        await interaction.response.send_modal(correct_modal)

        while not correct_modal.submitted:
            await asyncio.sleep(1)

        self.comment = correct_modal.comment.value
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = "cancel"
        self.stop()

@client.event
async def on_ready():
    # await client.tree.sync()
    state.init()
    _logger.info(f"{client.user} is ready and online!")

def extract_message_link_ids(url) -> tuple[int, int, int]:
    match = re.match(r"https://discord.com/channels/(\d+)/(\d+)/(\d+)", url)

    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    return None

async def get_message_from_link(message_link, wanted_guild_id) -> discord.Message:
    guild_id, channel_id, message_id = extract_message_link_ids(message_link)

    if not guild_id or guild_id != wanted_guild_id:
        return None

    channel = client.get_channel(channel_id)

    return await channel.fetch_message(message_id)

@client.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    setup_modal = Setup()
    await setup_modal.populate(interaction.guild.id)
    await interaction.response.send_modal(setup_modal)

@client.tree.command(name="bug")
@app_commands.describe(message_link='Message link to start reading from',
                       bug_hint='Hint with regards to the bug')
async def new_report(interaction: discord.Integration, message_link: str, bug_hint: Optional[str] = "None"):
    interaction.response.defer(ephemeral=True, thinking=True)

    if not await check_config(interaction, await state.get_config(interaction.guild.id)):
        return

    message = await get_message_from_link(message_link, interaction.guild.id)

    if not message:
        await interaction.response.send_message(f"Invalid message link!", ephemeral=True)
        return

    followup = interaction.followup
    guild_id = interaction.guild.id

    await interaction.response.send_message(f"Preparing bug report...", ephemeral=True)

    while await state.get_busy(guild_id):
        await asyncio.sleep(10)

    await state.set_busy(guild_id, True)

    try:
        combined_history = await chatproc.get_history(guild_id, message, 50, 3)
        analysis_suite = await state.get_analysis_suite(guild_id)

        issue_analysis = await analysis_suite.analyse_issue(combined_history, bug_hint)

        if issue_analysis == {}:
            await followup.send(f"No issues found in the chat log!", ephemeral=True)
            await state.set_busy(guild_id, False)
            return

        issue_title, issue_md = analysis_suite.make_markdown(issue_analysis)

        followup_message = None

        while True:
            confirm_view = Confirm()

            if not followup_message:
                followup_message = await followup.send(f"Confirm bug report?\n\n{issue_md}", view=confirm_view,
                                                    ephemeral=True)
            else:
                await followup_message.edit(content=f"Confirm bug report?\n\n{issue_md}", view=confirm_view)

            await confirm_view.wait()
            await followup_message.edit(view=None)

            match confirm_view.value:
                case "confirm":
                    issue_url = await file_issue(guild_id, issue_title, issue_md)
                    await followup.send(f"Bug report filed:\n{issue_url}")
                    break
                case "regenerate":
                    await followup_message.edit(content="Regenerating bug report...", view=None)
                    issue_analysis = await analysis_suite.analyse_issue(combined_history, bug_hint)
                    issue_title, issue_md = analysis_suite.make_markdown(issue_analysis)
                case "correct":
                    await followup_message.edit(content="Correcting bug report...", view=None)
                    issue_analysis = await analysis_suite.correct_issue(issue_analysis, confirm_view.comment)
                    issue_title, issue_md = analysis_suite.make_markdown(issue_analysis)
                case "cancel":
                    await followup.edit(content="Bug report cancelled!", view=None)
                    break
    except Exception as e:
        followup.send("There was an error filing the bug report, please contact bot admin.", ephemeral=True)
        _logger.exception(f"Error filing bug report:\n{e}")

    await state.set_busy(guild_id, False)

if __name__ == "__main__":
    client.run(os.getenv('DISCORD_TOKEN'))
