import re
from collections import defaultdict

def extract_config_parameters(config_file, output_file=None):
    """
    Extracts physical layer parameters for entities with PHY-MODEL PHY-ABSTRACT
    from the given configuration file.
    
    Args:
        config_file (str): Path to the config file (e.g., 'untitled_1.config')
        output_file (str, optional): If provided, writes the results to this file.
        
    Returns:
        list: A list of formatted strings containing the extracted parameters.
    """
    # Dictionary to hold parameters per identifier (the part in brackets)
    entities = defaultdict(dict)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Match lines with brackets, e.g., [ N8-190.0.1.0 ] PHY-MODEL PHY-ABSTRACT
            # or [SUB1/1/0] PHY-ABSTRACT-DATA-RATE 2000000.000000
            match = re.match(r'^\[\s*(.*?)\s*\]\s+(.*)', line)
            if match:
                identifier = match.group(1)
                rest_of_line = match.group(2)
                
                parts = rest_of_line.split()
                if len(parts) >= 2:
                    param_name = parts[0]
                    param_value = parts[1]
                    entities[identifier][param_name] = param_value
                    
    results = []
    
    # Filter entities that have PHY-MODEL set to PHY-ABSTRACT
    for identifier, params in entities.items():
        if params.get('PHY-MODEL') == 'PHY-ABSTRACT':
            # Extract requested values
            sinr = params.get('PHY-RX-SNR-THRESHOLD', 'N/A')
            tx_rate = params.get('PHY-ABSTRACT-DATA-RATE', 'N/A')
            rx_rate = tx_rate # Usually symmetric for abstract PHY
            tx_freq = params.get('PHY-ABSTRACT-CENTER-FREQUENCY', 'N/A')
            rx_freq = tx_freq # Usually symmetric
            tx_power = params.get('PHY-ABSTRACT-TX-POWER', 'N/A')
            rx_power = params.get('PHY-ABSTRACT-RX-SENSITIVITY', 'N/A')
            
            # Format output string
            result_str = (
                f"Name: [{identifier}], "
                f"SINR: {sinr}, "
                f"TxRate: {tx_rate}, "
                f"RxRate: {rx_rate}, "
                f"TxFreq: {tx_freq}, "
                f"RxFreq: {rx_freq}, "
                f"TxPower: {tx_power}, "
                f"RxPower: {rx_power}"
            )
            results.append(result_str)
            
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            for res in results:
                f.write(res + '\n')
        print(f"\n结果已保存到 {output_file}")
            
    return results

# Optional usage block
if __name__ == "__main__":
    results = extract_config_parameters('untitled_1.config', output_file='物理层数据采集2.txt')
    for res in results:
        print(res)
