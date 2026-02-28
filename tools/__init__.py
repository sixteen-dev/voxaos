from core.config import Config
from tools.executor import ToolExecutor
from tools.filesystem import list_directory, read_file, search_files, write_file
from tools.home_assistant import HomeAssistantTools
from tools.launcher import launch_app, open_url
from tools.process import kill_process, list_processes
from tools.shell import run_shell
from tools.web_search import fetch_page, web_search


def register_all_tools(executor: ToolExecutor, config: Config) -> None:
    executor.register("run_shell", run_shell)
    executor.register("read_file", read_file)
    executor.register("write_file", write_file)
    executor.register("list_directory", list_directory)
    executor.register("search_files", search_files)
    executor.register("list_processes", list_processes)
    executor.register("kill_process", kill_process)
    executor.register("launch_app", launch_app)
    executor.register("open_url", open_url)
    executor.register("web_search", web_search)
    executor.register("fetch_page", fetch_page)

    if config.home_assistant.enabled:
        ha = HomeAssistantTools(config.home_assistant)
        executor.register("ha_get_states", ha.ha_get_states)
        executor.register("ha_get_state", ha.ha_get_state)
        executor.register("ha_set_state", ha.ha_set_state)
        executor.register("ha_call_service", ha.ha_call_service)
        executor.register("ha_get_history", ha.ha_get_history)
