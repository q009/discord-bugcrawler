import common

from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

_logger = common.get_logger("Storage")

_mongo_client  = None

class Config:
    def __init__(self, data: dict = {}) -> None:
        if len(data) > 1:
            self.github_repo            = data.get("github_repo")
            self.product_name           = data.get("product_name")
            self.product_type           = data.get("product_type")
            self.issue_categories       = data.get("issue_categories")
            self.issue_extra_info       = data.get("issue_extra_info")
            self.discord_developer_role = data.get("discord_developer_role")
        else:
            self.github_repo            = ""
            self.product_name           = "Product Name"
            self.product_type           = "software"
            self.issue_categories       = []
            self.issue_extra_info       = []
            self.discord_developer_role = "Developer"

    def get_pretty_name(self, field: str) -> str:
        return {
            "github_repo"            : "GitHub Repository",
            "product_name"           : "Product Name",
            "product_type"           : "Product Type",
            "issue_categories"       : "Issue Categories",
            "issue_extra_info"       : "Issue Extra Information",
            "discord_developer_role" : "Discord Developer Role"
        }[field]

    def to_dict(self) -> dict:
        return {
            "github_repo"            : self.github_repo,
            "product_name"           : self.product_name,
            "product_type"           : self.product_type,
            "issue_categories"       : self.issue_categories,
            "issue_extra_info"       : self.issue_extra_info,
            "discord_developer_role" : self.discord_developer_role
        }

def init(mongo_uri: str) -> None:
    global _mongo_client
    _logger.info(f"Connecting to MongoDB...")
    _mongo_client = MongoClient(mongo_uri, server_api=ServerApi('1'))

    try:
        _mongo_client.admin.command('ping')
        _logger.info("Connection to MongoDB successful")
    except Exception as e:
        _logger.critical(e)

def _get_guild_info_collection() -> Collection:
    database = _mongo_client.get_database("discord_bugbot")
    return database.get_collection("guild_info")

def _add_document(collection : Collection, key: str) -> None:
    collection.insert_one({"_id" : key})

def _fetch(key: str) -> dict:
    object = {}

    collection =_get_guild_info_collection()
    object = collection.find_one(key)

    if object is None:
        _add_document(collection, key)
        return {"_id" : key}

    return object

def _push(key: str, object: dict) -> None:
    collection = _get_guild_info_collection()
    collection.update_one({"_id" : key}, { "$set": object }, upsert=True)

def init_config(guild_id: int) -> Config:
    _push(str(guild_id), Config().to_dict())

def get_config(guild_id: int) -> Config:
    return Config(_fetch(str(guild_id)))

def set_config(guild_id: int, config: Config) -> None:
    _push(str(guild_id), config.to_dict())
