from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import AGENT_CORE_ROOT
from app.rag.ingestion import load_local_documents
from app.rag.models import Chunk
from app.rag.service import RAGService


DEMO_TENANT_ID = "demo"
DEMO_ACCESS_ROLES = ["employee"]

RAW_DOCS = {
    "enterprise_kb": {
        "company_policy.md": (
            "# Company Policy\n\n"
            "餐饮报销上限为每人每餐 120 元，必须提交发票、参会人和业务目的。"
        )
    },
    "customer_support": {
        "enterprise_sla.txt": (
            "企业客户 P1 SLA 响应时间为 30 分钟。\n\n"
            "当企业客户提交 P1 工单时，支持团队必须在 30 分钟内完成首次响应，"
            "并同步值班经理跟进升级。"
        )
    },
    "ops_runbook": {
        "payment_runbook.md": (
            "# Payment Runbook\n\n"
            "支付错误码 PAY-502 表示支付网关超时。\n\n"
            "故障处理流程：检查支付网关健康状态、重试队列、第三方通道状态，"
            "必要时切换备用通道并记录事件。"
        )
    },
    "legal_contract": {
        "msa_terms.md": (
            "# MSA Terms\n\n"
            "合同责任上限为过去 12 个月已支付服务费总额。\n\n"
            "违约责任包括补救义务、损害赔偿和按合同约定承担的通知义务。"
        )
    },
    "data_analysis": {
        "sales_report.csv": (
            "month,region,revenue,orders\n"
            "2026-01,North,120000,480\n"
            "2026-02,North,135000,510\n"
            "2026-01,South,98000,430\n"
            "2026-02,South,101000,445\n"
        )
    },
}

EVAL_CASES = {
    "enterprise_kb": [
        {
            "query": "餐饮报销上限是多少？",
            "expected_domain": "enterprise_kb",
            "expected_source": "company_policy.md",
        }
    ],
    "customer_support": [
        {
            "query": "企业客户 P1 响应时间是多少？",
            "expected_domain": "customer_support",
            "expected_source": "enterprise_sla.txt",
        }
    ],
    "ops_runbook": [
        {
            "query": "支付错误码的故障处理流程是什么？",
            "expected_domain": "ops_runbook",
            "expected_source": "payment_runbook.md",
        }
    ],
    "legal_contract": [
        {
            "query": "合同责任上限和违约责任是什么？",
            "expected_domain": "legal_contract",
            "expected_source": "msa_terms.md",
        }
    ],
    "data_analysis": [
        {
            "query": "sales_report.csv 中有哪些销售字段？",
            "expected_domain": "data_analysis",
            "expected_source": "sales_report.csv",
        }
    ],
}


def main() -> None:
    data_dir = AGENT_CORE_ROOT / "data"
    raw_dir = data_dir / "raw"
    eval_dir = data_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    for domain, files in RAW_DOCS.items():
        domain_dir = raw_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (domain_dir / filename).write_text(content, encoding="utf-8")

    for domain, cases in EVAL_CASES.items():
        eval_path = eval_dir / f"{domain}_eval.jsonl"
        with eval_path.open("w", encoding="utf-8") as file:
            for case in cases:
                file.write(json.dumps(case, ensure_ascii=False) + "\n")

    chunks: list[Chunk] = []
    for domain in RAW_DOCS:
        chunks.extend(
            load_local_documents(
                raw_path=str(raw_dir / domain),
                tenant_id=DEMO_TENANT_ID,
                access_roles=DEMO_ACCESS_ROLES,
                domain=domain,
                glob_pattern="**/*",
            )
        )

    stats = RAGService().ingest_chunks(chunks, replace=True)
    print(f"created {stats['documents_loaded']} documents, {stats['chunks_created']} chunks")


if __name__ == "__main__":
    main()
