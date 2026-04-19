"""All-in-Prompt Retriever

把「所有候選」全部塞進 prompt 讓 LLM 自己挑。沒做任何前置過濾。

適合資料量小（幾十到一兩百筆）、又想省去 embedding 建置成本的場景。
目前虎尾地標辨識就是這種規模。
"""

from typing import Any, Callable

from ..data.base import DataSource


class AllInPromptRetriever:
    """把所有資料當 context 交給下游 Generator。

    這個 retriever 其實不做「檢索」，它是個直通層：
    只是讓所有 key 都被當成候選回傳。
    實際的「挑選」交給 Generator 在 prompt 裡做。

    Args:
        data_source: 資料來源
        key_field: 要回傳的 key 對應的欄位名（from each row）
        filter_fn: 選填，用來過濾掉不想納入候選的列（例如空白列）
    """

    def __init__(
        self,
        data_source: DataSource,
        key_field: str,
        filter_fn: Callable[[dict], bool] | None = None,
    ):
        self.data_source = data_source
        self.key_field = key_field
        self.filter_fn = filter_fn

    def retrieve(self, query: Any) -> list[str]:
        seen: set[str] = set()
        keys: list[str] = []
        for row in self.data_source.all_rows():
            if self.filter_fn and not self.filter_fn(row):
                continue
            key = (row.get(self.key_field) or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys
