import json, itertools, argparse, sys, time
import numpy as np

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

GRID_VISUAL = [1.50, 1.75, 2.00, 2.25, 2.50]
GRID_OCR    = [0.80, 0.95, 1.10, 1.20, 1.35]
GRID_ASR    = [0.75, 0.90, 1.00, 1.10, 1.20]


def search_with_weights(query, w_visual, w_ocr, w_asr, top_k, base_url, api_key=""):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        resp = requests.post(
            f"{base_url}/search",
            json={"query": query, "limit": top_k,
                  "rrf_weights": {"visual": w_visual, "ocr": w_ocr, "asr": w_asr}},
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data.get("kq", []))
    except Exception:
        return []


def compute_mrr(queries_gt, search_fn, top_k=10):
    mrrs = []
    for query, gt_frames in queries_gt.items():
        results = search_fn(query)
        result_paths = [r.get("filepath", r.get("id", "")) for r in results]
        gt_set = set(gt_frames)
        mrr = 0.0
        for rank, path in enumerate(result_paths[:top_k], 1):
            if path in gt_set:
                mrr = 1.0 / rank
                break
        mrrs.append(mrr)
    return float(np.mean(mrrs)) if mrrs else 0.0


def main():
    parser = argparse.ArgumentParser(description="Grid search RRF weights optimizing MRR")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--output", default="rrf_tuning_results.json")
    args = parser.parse_args()

    with open(args.queries, "r", encoding="utf-8") as f:
        queries_gt = json.load(f)

    total = len(GRID_VISUAL) * len(GRID_OCR) * len(GRID_ASR)
    print(f"Grid Search RRF Weights: {total} combinations x {len(queries_gt)} queries")
    print(f"Visual: {GRID_VISUAL}")
    print(f"OCR:    {GRID_OCR}")
    print(f"ASR:    {GRID_ASR}")

    best_mrr, best_weights, all_results = 0.0, None, []

    for idx, (wv, wo, wa) in enumerate(itertools.product(GRID_VISUAL, GRID_OCR, GRID_ASR), 1):
        def sfn(q, _wv=wv, _wo=wo, _wa=wa):
            return search_with_weights(q, _wv, _wo, _wa, args.top_k, args.server, args.api_key)

        mrr = compute_mrr(queries_gt, sfn, top_k=args.top_k)
        result = {"w_visual": wv, "w_ocr": wo, "w_asr": wa, "MRR": round(mrr, 4)}
        all_results.append(result)

        if mrr > best_mrr:
            best_mrr = mrr
            best_weights = result.copy()
            print(f"  [{idx:3d}/{total}] New best MRR={mrr:.4f} @ v={wv}, o={wo}, a={wa}")
        elif idx % 10 == 0:
            print(f"  [{idx:3d}/{total}] current best MRR={best_mrr:.4f}")

    all_results.sort(key=lambda x: x["MRR"], reverse=True)
    print("\nTOP 5:")
    for i, r in enumerate(all_results[:5], 1):
        print(f"  {i}. MRR={r['MRR']:.4f} v={r['w_visual']} o={r['w_ocr']} a={r['w_asr']}")

    if best_weights:
        print(f"\nBest weights -> update backend/main.py:")
        print(f"  w_visual = {best_weights['w_visual']}")
        print(f"  w_ocr    = {best_weights['w_ocr']}")
        print(f"  w_asr    = {best_weights['w_asr']}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"best_weights": best_weights, "best_mrr": round(best_mrr,4),
                   "n_queries": len(queries_gt), "top_k": args.top_k,
                   "all_results": all_results}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
