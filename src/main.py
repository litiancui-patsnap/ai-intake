"""AI信息摄入系统 - 主程序"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import classify, dedup, ingest, publish, score, storage, summarize
from .utils import Config, get_logger, setup_logger


def parse_time_delta(time_str: str) -> timedelta:
    """解析时间增量字符串

    Args:
        time_str: 时间字符串，如 "24h", "7d", "48h"

    Returns:
        timedelta对象
    """
    if time_str.endswith("h"):
        hours = int(time_str[:-1])
        return timedelta(hours=hours)
    elif time_str.endswith("d"):
        days = int(time_str[:-1])
        return timedelta(days=days)
    else:
        raise ValueError(f"无效的时间格式: {time_str}，应为 '24h' 或 '7d'")


def run_daily(args):
    """运行日报生成

    Args:
        args: 命令行参数
    """
    logger = get_logger()
    started_at = datetime.now()

    logger.info("=" * 60)
    logger.info("开始生成日报")
    logger.info("=" * 60)

    try:
        # 加载配置
        config = Config(args.config_dir)

        # 初始化存储
        db_path = Path(args.config_dir) / "ai-intake.db"
        store = storage.Storage(str(db_path))

        # 计算时间范围
        since_delta = parse_time_delta(args.since)
        since = datetime.now() - since_delta

        # 1. 采集
        logger.info(f"步骤 1/7: 采集信息源 (时间范围: {args.since})")
        sources = config.get_enabled_sources()
        logger.info(f"已启用 {len(sources)} 个信息源")

        network_config = config.get_network_config()
        items = ingest.fetch_all(sources, network_config)

        if not items:
            logger.warning("未采集到任何数据，终止")
            return

        # 2. 去重
        logger.info("步骤 2/7: 去重")
        # 获取历史数据用于去重
        dedup_config = config.get_dedup_config()
        lookback_days = dedup_config.get("lookback_days", 30)
        history_since = datetime.now() - timedelta(days=lookback_days)
        existing_items = store.get_items(since=history_since)
        logger.info(f"加载 {len(existing_items)} 条历史数据用于去重")

        items = dedup.deduplicate(items, existing_items, dedup_config)

        if not items:
            logger.warning("去重后无数据，终止")
            return

        # 3. 分类
        logger.info("步骤 3/7: 分类")
        items = classify.classify_batch(items, config.topics)

        # 4. 评分
        logger.info("步骤 4/7: 评分")
        scoring_config = config.get_scoring_config()
        preferences = config.get_preferences()
        items = score.score_batch(items, scoring_config, config.topics, preferences)

        # 5. 标记必读
        logger.info("步骤 5/7: 标记必读")
        must_read_rules = config.get_must_read_rules()
        topics_dict = {t["name"]: t for t in config.topics}
        items = score.mark_must_read(items, must_read_rules, topics_dict)

        # 6. 生成摘要
        if not args.no_summary:
            logger.info("步骤 6/7: 生成摘要")
            llm_config = config.get_llm_config()
            items = summarize.summarize_batch(items, llm_config)
        else:
            logger.info("步骤 6/7: 跳过摘要生成 (--no-summary)")

        # 7. 发布
        logger.info("步骤 7/7: 生成报告")
        output_dir = Path(args.output_dir) / "daily"
        output_config = config.get_output_config("daily")

        # 限制输出数量
        if args.limit:
            items = items[: args.limit]

        report_path = publish.generate_daily_report(items, str(output_dir), datetime.now(), output_config)

        logger.info(f"✅ 日报已生成: {report_path}")

        # 保存到数据库
        if not args.dry_run:
            logger.info("保存到数据库...")
            store.save_items(items)

            # 记录运行日志
            finished_at = datetime.now()
            store.log_run(
                run_type="daily",
                started_at=started_at,
                finished_at=finished_at,
                items_collected=len(items),
                items_published=len(items),
                status="success",
            )
        else:
            logger.info("Dry-run模式，跳过数据库保存")

        # 可选：导出JSONL
        if args.export_jsonl:
            jsonl_path = Path(args.output_dir) / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            store.export_jsonl(items, str(jsonl_path))
            logger.info(f"已导出JSONL: {jsonl_path}")

        store.close()

        logger.info("=" * 60)
        logger.info("日报生成完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"生成日报失败: {e}", exc_info=True)
        sys.exit(1)


def run_weekly(args):
    """运行周报生成

    Args:
        args: 命令行参数
    """
    logger = get_logger()
    started_at = datetime.now()

    logger.info("=" * 60)
    logger.info("开始生成周报")
    logger.info("=" * 60)

    try:
        # 加载配置
        config = Config(args.config_dir)

        # 初始化存储
        db_path = Path(args.config_dir) / "ai-intake.db"
        store = storage.Storage(str(db_path))

        # 计算时间范围
        since_delta = parse_time_delta(args.since)
        since = datetime.now() - since_delta

        # 从数据库查询一周内的数据
        logger.info(f"从数据库查询数据 (时间范围: {args.since})")
        items = store.get_items(since=since)

        if not items:
            logger.warning("数据库中无数据，尝试实时采集...")

            # 实时采集
            sources = config.get_enabled_sources()
            network_config = config.get_network_config()
            items = ingest.fetch_all(sources, network_config)

            if not items:
                logger.error("仍无数据，终止")
                return

            # 处理流程（简化版）
            dedup_config = config.get_dedup_config()
            items = dedup.deduplicate(items, None, dedup_config)
            items = classify.classify_batch(items, config.topics)

            scoring_config = config.get_scoring_config()
            preferences = config.get_preferences()
            items = score.score_batch(items, scoring_config, config.topics, preferences)

            must_read_rules = config.get_must_read_rules()
            topics_dict = {t["name"]: t for t in config.topics}
            items = score.mark_must_read(items, must_read_rules, topics_dict)

        logger.info(f"共 {len(items)} 条数据")

        # 限制输出数量
        if args.limit:
            items = items[: args.limit]

        # 生成周报
        output_dir = Path(args.output_dir) / "weekly"
        output_config = config.get_output_config("weekly")

        # 计算本周开始日期（周一）
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())

        report_path = publish.generate_weekly_report(items, str(output_dir), week_start, output_config)

        logger.info(f"✅ 周报已生成: {report_path}")

        # 记录运行日志
        if not args.dry_run:
            finished_at = datetime.now()
            store.log_run(
                run_type="weekly",
                started_at=started_at,
                finished_at=finished_at,
                items_collected=len(items),
                items_published=len(items),
                status="success",
            )

        store.close()

        logger.info("=" * 60)
        logger.info("周报生成完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"生成周报失败: {e}", exc_info=True)
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AI信息摄入系统 - 为工程师打造的低噪音AI信息订阅系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version="ai-intake 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # daily 命令
    daily_parser = subparsers.add_parser("daily", help="生成日报")
    daily_parser.add_argument(
        "--since",
        type=str,
        default="24h",
        help="采集时间范围 (例如: 24h, 48h, 7d)",
    )
    daily_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="输出条目数量限制",
    )
    daily_parser.add_argument(
        "--config-dir",
        type=str,
        default=".",
        help="配置文件目录路径",
    )
    daily_parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="输出目录路径",
    )
    daily_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run模式，不写入数据库",
    )
    daily_parser.add_argument(
        "--no-summary",
        action="store_true",
        help="跳过LLM摘要生成",
    )
    daily_parser.add_argument(
        "--export-jsonl",
        action="store_true",
        help="导出JSONL格式",
    )
    daily_parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志输出",
    )

    # weekly 命令
    weekly_parser = subparsers.add_parser("weekly", help="生成周报")
    weekly_parser.add_argument(
        "--since",
        type=str,
        default="7d",
        help="查询时间范围 (例如: 7d, 14d)",
    )
    weekly_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="输出条目数量限制",
    )
    weekly_parser.add_argument(
        "--config-dir",
        type=str,
        default=".",
        help="配置文件目录路径",
    )
    weekly_parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="输出目录路径",
    )
    weekly_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run模式",
    )
    weekly_parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志输出",
    )

    args = parser.parse_args()

    # 设置日志级别
    if hasattr(args, "verbose") and args.verbose:
        import logging

        setup_logger(level=logging.DEBUG)
    else:
        import logging

        setup_logger(level=logging.INFO)

    # 执行命令
    if args.command == "daily":
        run_daily(args)
    elif args.command == "weekly":
        run_weekly(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
