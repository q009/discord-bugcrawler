import asyncio
import common
import gpt
import json
import state

_logger = common.get_logger("Analysis")

PROMPT_DIR = "prompts"

# Common prompts
_prompt_field_names    = None
_prompt_analyse_images = None
_prompt_correct        = None

with open(f"{PROMPT_DIR}/field_names.txt", "r") as file:
    _prompt_field_names = file.read()

with open(f"{PROMPT_DIR}/analyse_images.txt", "r") as file:
    _prompt_analyse_images = file.read()

with open(f"{PROMPT_DIR}/correct.txt", "r") as file:
    _prompt_correct = file.read()

async def _get_field_names(info: list[str]) -> dict:
    field_list = ""
    field_num = 1

    for field in info:
        field_list += f"{field_num}) {field}\n"

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, gpt.request_json, _prompt_field_names, field_list)

STANDARD_REPORT_INFO = [
    "Product version (build, version, commit hash, etc.)",
    "A thorough description of the issue, detailing how and when it occurs",
    "Attempted workarounds",
]

STANDARD_REPORT_INFO_JSON = {
    "title": "Title",
    "category": "Category",
    "description": "Description",
    "workarounds": "Workarounds",
    "version": "Product version"
}

class AnalysisSuite:
    def __init__(self, guild_id: int) -> None:
        self._prompt_analyse_chat = None
        self._prompt_format_json  = None
        self._field_names         = None
        self._guild_id            = guild_id

    async def _init(self) -> None:
        await self._init_fields()
        await self._init_prompts()

    async def _init_fields(self) -> None:
        config = await state.get_config(self._guild_id)
        self.field_names = await _get_field_names(config.issue_extra_info)

        if self.field_names == {}:
            RuntimeError("Failed to get field names")

        self._field_names = {**self.field_names, **STANDARD_REPORT_INFO_JSON}

    async def _init_analyse_chat_prompt(self) -> None:
        info_list     = ""
        category_list = ""

        config = await state.get_config(self._guild_id)

        issue_info = STANDARD_REPORT_INFO + config.issue_extra_info

        for field in issue_info:
            if info_list != "":
                info_list += "\n* " + field
            else:
                info_list += "* " + field

        for category in config.issue_categories:
            if category_list != "":
                category_list += "\n  - " + category
            else:
                category_list += "  - " + category

        with open(f"{PROMPT_DIR}/analyse_chat.txt", "r") as file:
            self._prompt_analyse_chat = file.read()

        self._prompt_analyse_chat = self._prompt_analyse_chat.replace("@product_name@", config.product_name)
        self._prompt_analyse_chat = self._prompt_analyse_chat.replace("@product_type@", config.product_type)
        self._prompt_analyse_chat = self._prompt_analyse_chat.replace("@info@",         info_list)
        self._prompt_analyse_chat = self._prompt_analyse_chat.replace("@categories@",   category_list)

    def _init_format_json_prompt(self) -> None:
        format_fields = ""

        for key in self._field_names:
            if format_fields != "":
                format_fields += ",\n    " + '"' + key + '": "..."'
            else:
                format_fields += '"' + key + '": "..."'

        with open(f"{PROMPT_DIR}/format_json.txt", "r") as file:
            self._prompt_format_json = file.read()

        self._prompt_format_json = self._prompt_format_json.replace("@fields@", format_fields)

    async def _init_prompts(self) -> None:
        await self._init_analyse_chat_prompt()
        self._init_format_json_prompt()

    async def analyse_images(self, chat_log: str, image_urls: list[str]) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, gpt.request, _prompt_analyse_images, chat_log, image_urls, 0.33,
                                          "gpt-4-vision-preview")

    async def analyse_issue(self, chat_log: str, hint: str) -> dict:
        analysis_input = "Chat log:\n```\n" + chat_log + "\n```\n\n"
        analysis_input += f"Developer hint: {hint if hint != '' else '<None>'}"

        loop = asyncio.get_event_loop()

        analysis = await loop.run_in_executor(None, gpt.request, self._prompt_analyse_chat, analysis_input)

        return await loop.run_in_executor(None, gpt.request_json, self._prompt_format_json, analysis)

    async def correct_analysis(self, analysis: dict, comment: str) -> dict:
        correct_input = "```json\n"
        correct_input += json.dumps(analysis, indent=4, ensure_ascii=False)
        correct_input += "```\n\nComment: " + comment

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(None, gpt.request_json, _prompt_correct, correct_input, "gpt-4-turbo-preview")

    def make_markdown(self, issue: dict) -> tuple[str, str]:
        if "category" not in issue:
            _logger.info("No issue to format")
            return None

        issue_title = f"[BUGBOT][{issue['category']}] {issue['title']}"

        issue_md = f"# {issue_title}\n\n"

        issue_md += "## Description\n"
        issue_md += issue["description"] + "\n\n"

        issue_md += "## Workarounds\n"
        issue_md += issue["workarounds"] + "\n\n"

        issue_md += "## Information"

        for key in issue:
            if key == "category" or key == "title" or key == "description" or key == "workarounds":
                continue

            issue_md += "\n * " + self._field_names[key] + ": " + issue[key]

        return issue_title, issue_md
