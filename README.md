# Discord Bugcrawler v0.0.1

## Description
This is a simple bot that is used to automate filing of GitHub issues by scraping the Discord chat.
It uses OpenAI's GPT-4 Turbo to analyze the chat and images to gather the information about the issues and then
generates a markdown that is then posted on GitHub issues.

## Prerequisites
- OpenAI API account with access to GPT-4 Turbo
- Discord bot token
- GitHub App registered and added to wanted repositories
- MongoDB database

## Required packages
- Python 3.10 or higher
- Libraries listed in `requirements.txt`

## Deployment

1. Create a directory in the root of the project called ``certs/`` and place your GitHub App private key there.
2. In the project directory create a ``.env`` file that should contain:
    * ``DISCORD_TOKEN=`` - Discord app token
    * ``OPENAI_API_KEY=`` - OpenAI API key with access to GPT-4 Turbo
    * ``GITHUB_APP_ID=`` - GitHub App ID
    * ``GITHUB_APP_KEY=`` - Name of your GitHub App private key file that you placed in the ``certs/`` directory
    * ``MONGO_URI=`` - MongoDB connection URI
3. Run the bot with ``python main.py``
4. Invite the bot to your Discord server

## Configuration
To configure the bot simply call ``/setup`` command in Discord. You will be asked to fill the following:
1. GitHub repository name.
    ```
        owner/repo
    ```
2. Product name and type in separate lines.
    ```
        Best Game Ever
        video game
    ```
3. Issue categories in separate lines.
    ```
        UI
        Performance
        Other
    ```
4. Additional information to collect for the issue in separate lines.
    ```
        Hardware and drivers
        Operating system
    ```

    Standard information that is always collected and doesn't need to be specified in this configuration step:
    - Product version
    - Description
    - Workarounds
5. Name of the Discord developer role, to distinguish them in the chat.
    ```
        Developer
    ```

## Usage
Find the message that begins the conversation about the issue you want to report, copy link to it and call ``/bug`` with the link as an argument.
You may also give it an optional ``bug_hint`` argument to help the bot understand the issue better.
