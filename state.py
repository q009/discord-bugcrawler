import asyncio
import common
import storage
import time

from storage import Config
from analysis import AnalysisSuite

# Purge old states after 2 days of inactivity
_PURGE_TIME_S = 60 * 60 * 24 * 2

_logger = common.get_logger("State")

_lock = asyncio.Lock()
_states = {}

class State:
    def __init__(self, guild_id: int) -> None:
        self._guild_id       = guild_id
        self._analysis_suite = AnalysisSuite(guild_id)
        self._config         = storage.get_config(guild_id)
        self._last_use       = time.time()
        self._busy           = False

    async def _init(self) -> None:
        await self._analysis_suite._init()

    def _update_last_use(self) -> None:
        self._last_use = time.time()

    def _set_config(self, config: Config) -> None:
        self._config = config
        self._update_last_use()

    def _get_analysis_suite(self) -> AnalysisSuite:
        self._update_last_use()
        return self._analysis_suite

    def _get_config(self) -> Config:
        self._update_last_use()
        return self._config

async def _purge_states() -> None:
    global _states

    _logger.debug("Checking for states to purge...")

    async with _lock:
        for guild_id in list(_states):
            state = _states[guild_id]
            if time.time() - state._last_use > _PURGE_TIME_S and not state._busy:
                _logger.info(f"Purging state for guild {guild_id}")
                del _states[guild_id]

    await asyncio.sleep(60 * 10)
    await _purge_states()

# Start purging states
_purge_states()

async def _get_state(guild_id: int) -> State:
    global _states
    state = None
    needs_init = False

    async with _lock:
        if guild_id not in _states:
            state = _states[guild_id] = State(guild_id)
            needs_init = True
        else:
            state = _states[guild_id]

    state._update_last_use()

    if needs_init:
        await state._init()

    return state

async def get_analysis_suite(guild_id: int) -> AnalysisSuite:
    state = await _get_state(guild_id)
    return state._get_analysis_suite()

async def get_config(guild_id: int) -> Config:
    state = await _get_state(guild_id)
    return state._get_config()

async def set_config(guild_id: int, config: Config) -> None:
    state = await _get_state(guild_id)
    state._set_config(config)
    storage.set_config(guild_id, config)

purge_task = None
def init() -> None:
    global purge_task
    purge_task = asyncio.create_task(_purge_states())

async def set_busy(guild_id: int, busy: bool) -> None:
    state = await _get_state(guild_id)
    state._busy = busy

async def get_busy(guild_id: int) -> bool:
    state = await _get_state(guild_id)
    return state._busy
