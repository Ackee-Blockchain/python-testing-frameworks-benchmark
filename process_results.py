import csv
import statistics
import argparse

"""
Processes csv file with the following format:
brownie,anvil,35.954660177230835
brownie,anvil,35.53314709663391
brownie,development,54.45306158065796
brownie,development,53.407734870910645

Computes avg, median, and stdev for each framework/network combination
"""


def load_results(file):
    """
    Loads results from csv file.
    """
    replacements_dir = {
        "development": "ganache",
        "ethereum:local:foundry": "anvil",
        "ethereum:local:hardhat": "hardhat",
        "ethereum:local:ganache": "ganache"
    }

    results = []
    with open(file, newline="") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row:
                continue
            framework, network, time = row
            if network in replacements_dir:
                network = replacements_dir[network]
            results.append((framework, network, time))
    return results



def process_results(res):
    """
    Processes results into a dictionary with avg time, stdev, and median
    """
    processed_res = {}
    for row in res:
        framework, network, time = row
        if framework not in processed_res:
            processed_res[framework] = {}
        if network not in processed_res[framework]:
            processed_res[framework][network] = []
        processed_res[framework][network].append(float(time))
    for framework in processed_res:
        for network in processed_res[framework]:
            processed_res[framework][network] = {
                "avg": statistics.mean(processed_res[framework][network]),
                "stdev": statistics.stdev(processed_res[framework][network]),
                "median": statistics.median(processed_res[framework][network])
            }
    return processed_res


def print_results(processed_res):
    """
    Prints processed results in Markdown format to stdout. Prints out frameworks in columns, networks in rows with
    values being the avg times with stdev in parentheses.
    """
    frameworks = list(processed_res.keys())
    networks = list(processed_res[frameworks[0]].keys())
    print("| / |", end="")
    for framework in frameworks:
        print(f" {framework} |", end="")
    print("")
    print("| --- |", end="")
    for _ in frameworks:
        print(" --- |", end="")
    print("")
    for network in networks:
        print(f"| {network} |", end="")
        for framework in frameworks:
            print(f" {processed_res[framework][network]['avg']:.2f} ({processed_res[framework][network]['stdev']:.2f}) |", end="")
        print("")

def write_results(processed_res):
    """
    Writes results to csv file
    """
    with open("processed_results.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["framework", "network", "avg", "stdev", "median"])
        for framework in processed_res:
            for network in processed_res[framework]:
                writer.writerow([framework, network, processed_res[framework][network]['avg'], processed_res[framework][network]['stdev'], processed_res[framework][network]['median']])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="file to process")
    args = parser.parse_args()

    res = load_results(args.file)
    processed_res = process_results(res)
    print_results(processed_res)
    write_results(processed_res)


if __name__ == "__main__":
    main()
