import json, time, argparse, sys
import numpy as np

try:
    import requests
except ImportError:
    print("Missing requests. pip install requests", file=sys.stderr)
    sys.exit(1)


def eval_retrieval(queries_gt, search_fn, top_k=10):
    recalls = {1: [], 5: [], 10: []}
    mrrs, latencies = [], []
    empty_results = 0
    for query, gt_frames in queries_gt.items():
        t0 = time.perf_counter()
        try:
            results = search_fn(query, top_k=top_k)
        except Exception as e:
            print(f"  Query failed: {str(e)}", file=sys.stderr)
            results = []
        latencies.append(time.perf_counter() - t0)
        if not results:
            empty_results += 1
            for k in [1, 5, 10]:
                recalls[k].append(0.0)
            mrrs.append(0.0)
            continue
        result_paths = [r.get("filepath", r.get("id", "")) for r in results]
        gt_set = set(gt_frames)
        for k in [1, 5, 10]:
            hit = any(p in gt_set for p in result_paths[:k])
            recalls[k].append(1.0 if hit else 0.0)
        mrr_score = 0.0
        for rank, path in enumerate(result_paths, 1):
            if path in gt_set:
                mrr_score = 1.0 / rank
                break
        mrrs.append(mrr_score)
    return {
        "n_queries": len(queries_gt), "empty_results": empty_results,
        "Recall@1":  round(float(np.mean(recalls[1])), 4),
        "Recall@5":  round(float(np.mean(recalls[5])), 4),
        "Recall@10": round(float(np.mean(recalls[10])), 4),
        "MRR":       round(float(np.mean(mrrs)), 4),
        "Latency_P50_ms": round(float(np.percentile(latencies, 50)) * 1000, 1),
        "Latency_P95_ms": round(float(np.percentile(latencies, 95)) * 1000, 1),
        "Latency_P99_ms": round(float(np.percentile(latencies, 99)) * 1000, 1),
    }


def eval_asr_wer(predictions, ground_truth):
    """Tinh WER cho ASR. Can: pip install jiwer"""
    try:
        from jiwer import wer
    except ImportError:
        return {"error": "pip install jiwer"}
    refs = [ground_truth[v] for v in ground_truth]
    hyps = [predictions.get(v, "") for v in ground_truth]
    return {"WER": round(wer(refs, hyps), 4), "n_samples": len(refs)}


def make_http_search_fn(base_url="http://localhost:8000", api_key=""):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    def search_fn(query, top_k=10):
        try:
            resp = requests.post(
                f"{base_url}/search",
                json={"query": query, "limit": top_k},
                headers=headers, timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data.get("kq", []))
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP search failed: {e}")
    return search_fn


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Video Retrieval - Recall@K, MRR, Latency P50/P95/P99"
    )
    parser.add_argument("--queries", required=True, help="Path to validation_queries.json")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    try:
        with open(args.queries, "r", encoding="utf-8") as f:
            queries_gt = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {args.queries}", file=sys.stderr)
        print('Create validation_queries.json: {"query text": ["video/frame.webp"]}')
        sys.exit(1)

    print(f"Benchmark: {len(queries_gt)} queries, top_k={args.top_k}, server={args.server}")

    try:
        requests.get(f"{args.server}/health", timeout=5).raise_for_status()
        print("Server connected OK")
    except Exception as e:
        print(f"Cannot connect to server: {e}")
        print("Start server: python -m uvicorn backend.main:app")
        sys.exit(1)

    metrics = eval_retrieval(queries_gt, make_http_search_fn(args.server, args.api_key), top_k=args.top_k)

    print("=" * 50)
    for key, val in metrics.items():
        print(f"  {key:25s}: {val}")
    print("=" * 50)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
