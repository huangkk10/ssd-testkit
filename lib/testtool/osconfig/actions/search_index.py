"""
OsConfig — SearchIndexAction

Disables the Windows Search service (WSearch), which powers the
Windows Search index. Disabling it reduces background I/O and CPU
usage on test machines where search is not required.

Service: WSearch
Registry key: HKLM\\SYSTEM\\CurrentControlSet\\Services\\WSearch
"""

from ._base_service_action import BaseServiceAction


class SearchIndexAction(BaseServiceAction):
    """Disable Windows Search Index (WSearch service)."""

    name = "SearchIndexAction"
    service_name = "WSearch"
    capability_key = "search_index"
