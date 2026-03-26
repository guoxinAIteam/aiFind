from fastapi import APIRouter, File, UploadFile, HTTPException

from backend.services.cbss_doc_parser import parse_cbss_docx

router = APIRouter(prefix="/api/doc", tags=["doc"])


@router.post("/parse")
async def parse_doc(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文档")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    # python-docx 需要文件路径或类文件对象；这里用内存 bytes 包装
    import io

    bio = io.BytesIO(content)
    try:
        result = parse_cbss_docx(bio)  # type: ignore[arg-type]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

    return result

