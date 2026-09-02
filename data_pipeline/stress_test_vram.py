import asyncio, json, time, argparse, sys
import numpy as np

try:
    import websockets
except ImportError:
    print("pip install websockets", file=sys.stderr)
    sys.exit(1)


async def run_single_client(client_id, ws_url, query, api_key="", timeout_s=30.0):
    url = ws_url + (f"?token={api_key}" if api_key else "")
    result = {"client_id": client_id, "success": False, "n_results": 0,
               "latency_ms": None, "error": None}
    t0 = time.perf_counter()
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            await ws.send(json.dumps({"type": "search", "query": query, "limit": 20}))
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
            latency_ms = (time.perf_counter() - t0) * 1000
            data = json.loads(raw)
            n_res = len(data.get("kq", data.get("results", [])))
            result.update({"success": True, "n_results": n_res, "latency_ms": round(latency_ms, 1)})
    except asyncio.TimeoutError:
        result["error"] = f"Timeout after {timeout_s}s"
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


async def stress_test(n_clients, ws_url, queries, api_key="", timeout_s=30.0):
    print(f"Stress test: {n_clients} concurrent clients | URL: {ws_url}")
    client_queries = [queries[i % len(queries)] for i in range(n_clients)]
    tasks = [run_single_client(i, ws_url, q, api_key, timeout_s)
             for i, q in enumerate(client_queries)]
    t_start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    total_time = (time.perf_counter() - t_start) * 1000
    return results, total_time


def print_report(results, total_time_ms):
    n = len(results)
    successes = [r for r in results if r["success"]]
    failures  = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in successes if r["latency_ms"]]

    print("=" * 55)
    print("STRESS TEST RESULTS")
    print("=" * 55)
    print(f"  Total clients:   {n}")
    print(f"  Success:         {len(successes)} ({len(successes)/n*100:.0f}%)")
    print(f"  Failed/Timeout:  {len(failures)}  ({len(failures)/n*100:.0f}%)")
    print(f"  Total wall time: {total_time_ms:.0f}ms")
    if latencies:
        print(f"  Latency P50:     {np.percentile(latencies, 50):.0f}ms")
        print(f"  Latency P95:     {np.percentile(latencies, 95):.0f}ms")
        print(f"  Latency P99:     {np.percentile(latencies, 99):.0f}ms")
        print(f"  Latency max:     {max(latencies):.0f}ms")
        print(f"  Avg results/q:   {np.mean([r['n_results'] for r in successes]):.1f}")
    if failures:
        print("\n  Errors:")
        for r in failures[:5]:
            print(f"    Client {r['client_id']:2d}: {r['error']}")
    print("=" * 55)
    print("Check server log for '[VRAM] current=... | peak=...'")


def main():
    parser = argparse.ArgumentParser(description="Stress test VRAM with N concurrent WebSocket clients")
    parser.add_argument("--n-clients", type=int, default=5)
    parser.add_argument("--queries", nargs="+", default=[
        "nguoi di xe may tren duong pho",
        "bien hieu nha hang xuat hien tren man hinh",
        "nguoi phu nu mac ao trang ngoi trong xe o to",
        "tre em choi dua trong cong vien",
        "dam dong tap trung tai quang truong",
    ])
    parser.add_argument("--queries-file", default="")
    parser.add_argument("--ws-url", default="ws://localhost:8000/ws")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    queries = args.queries
    if args.queries_file:
        try:
            with open(args.queries_file, "r", encoding="utf-8") as f:
                queries = [l.strip() for l in f if l.strip()]
            print(f"Loaded {len(queries)} queries from {args.queries_file}")
        except FileNotFoundError:
            print(f"queries_file not found, using default queries")

    results, total_time = asyncio.run(
        stress_test(args.n_clients, args.ws_url, queries, args.api_key, args.timeout)
    )
    print_report(results, total_time)


if __name__ == "__main__":
    main()
