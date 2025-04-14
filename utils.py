from typing import Dict, List, Any, Optional

def simplify_cosmos_item(item: Dict[str, Any], custom_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """データベース結果を簡略化します。"""
    excluded_fields = {
        "systemInfo",
        "departmentCustomFields.productCategoryVector",
        "_rid",
        "_self",
        "_etag",
        "_attachments",
        "_ts"
    }
    
    # custom_fieldsがNoneでなければその内容をexcluded_fieldsに追加
    if custom_fields is not None:
        excluded_fields.update(custom_fields)
    
    try:
        if isinstance(item, dict):
            return {k: v for k, v in item.items() if k not in excluded_fields}
        return item  # itemが辞書でない場合はそのまま返す
    except AttributeError as e:
        raise AttributeError(f"Failed to filter: {str(e)}") from e