import re
import math
from itertools import combinations

def calculate_azimuth(x1, y1, x2, y2):
    """
    Calculate geographic azimuth from (x1,y1) to (x2,y2).
    0 degrees is North (positive Y axis), increasing clockwise.
    """
    dx = x2 - x1
    dy = y2 - y1
    azimuth = math.degrees(math.atan2(dx, dy))
    return (azimuth + 360) % 360

def calculate_elevation(x1, y1, z1, x2, y2, z2):
    """
    Calculate elevation angle from (x1,y1,z1) to (x2,y2,z2).
    Positive angle means looking up, negative means looking down.
    """
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    horizontal_distance = math.sqrt(dx**2 + dy**2)
    elevation = math.degrees(math.atan2(dz, horizontal_distance))
    return elevation

def parse_config_links(config_file):
    # Store sets of connected nodes
    connected_groups = []
    
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Match SUBNET or LINK
            if line.startswith('SUBNET') or line.startswith('LINK'):
                # Extract nodes inside { }
                match = re.search(r'\{\s*([\d\s,]+)\s*\}', line)
                if match:
                    nodes_str = match.group(1)
                    nodes = [int(n.strip()) for n in nodes_str.split(',')]
                    connected_groups.append(set(nodes))
                    
    return connected_groups

def parse_node_positions(nodes_file):
    positions = {}
    with open(nodes_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Example: 1 0 (12.4946, 53.1622, 260.0) 0 0 0
            match = re.match(r'^(\d+)\s+0S?\s+\(([^,]+),\s*([^,]+),\s*([^)]+)\)', line)
            if match:
                node_id = int(match.group(1))
                if node_id not in positions: # Only take the first position (time 0)
                    x = float(match.group(2))
                    y = float(match.group(3))
                    z = float(match.group(4))
                    positions[node_id] = (x, y, z)
    return positions

def process_link_relationships(config_file, nodes_file, output_file=None):
    """
    Parses subnet/link connections from the config file and node positions from the nodes file,
    calculates pairwise azimuths and determines if nodes are neighbors.
    
    Args:
        config_file (str): Path to the config file (e.g., 'scene3.config')
        nodes_file (str): Path to the nodes file (e.g., 'scene3.nodes')
        output_file (str, optional): If provided, writes the results to this file.
        
    Returns:
        list: A list of dictionaries containing the relationship details for each node pair.
    """
    # 1. Parse connected groups from config
    connected_groups = parse_config_links(config_file)
    
    # 2. Parse positions from nodes file
    positions = parse_node_positions(nodes_file)
    
    # Get all unique nodes
    all_nodes = sorted(positions.keys())
    
    results = []
    
    for n1, n2 in combinations(all_nodes, 2):
        # Check neighbor status
        is_neighbor = False
        for group in connected_groups:
            if n1 in group and n2 in group:
                is_neighbor = True
                break
        
        # Get positions
        pos1 = positions[n1]
        pos2 = positions[n2]
        
        # Calculate azimuths (Geographic: North=0, Clockwise)
        azimuth1 = calculate_azimuth(pos1[0], pos1[1], pos2[0], pos2[1])
        azimuth2 = calculate_azimuth(pos2[0], pos2[1], pos1[0], pos1[1])
        
        # Calculate elevations
        elevation1 = calculate_elevation(pos1[0], pos1[1], pos1[2], pos2[0], pos2[1], pos2[2])
        elevation2 = calculate_elevation(pos2[0], pos2[1], pos2[2], pos1[0], pos1[1], pos1[2])
        
        # Format output
        pos1_str = f"({pos1[0]:.4f}, {pos1[1]:.4f}, {pos1[2]:.4f})"
        pos2_str = f"({pos2[0]:.4f}, {pos2[1]:.4f}, {pos2[2]:.4f})"
        
        result_dict = {
            'Node1': n1,
            'Node2': n2,
            'Is_Neighbor': is_neighbor,
            'Node1_Pos': pos1_str,
            'Node2_Pos': pos2_str,
            'Azimuth_1_to_2': round(azimuth1, 2),
            'Azimuth_2_to_1': round(azimuth2, 2),
            'Elevation_1_to_2': round(elevation1, 2),
            'Elevation_2_to_1': round(elevation2, 2)
        }
        results.append(result_dict)
        
    # 3. Write to file if specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Header
            header = "Node1\tNode2\tIs_Neighbor\tNode1_Pos(x,y,z)\tNode2_Pos(x,y,z)\tAzimuth_1_to_2(deg)\tAzimuth_2_to_1(deg)\tElevation_1_to_2(deg)\tElevation_2_to_1(deg)\n"
            f.write(header)
            
            for res in results:
                line = f"{res['Node1']}\t{res['Node2']}\t{res['Is_Neighbor']}\t{res['Node1_Pos']}\t{res['Node2_Pos']}\t{res['Azimuth_1_to_2']:.2f}\t{res['Azimuth_2_to_1']:.2f}\t{res['Elevation_1_to_2']:.2f}\t{res['Elevation_2_to_1']:.2f}\n"
                f.write(line)
                
    return results

if __name__ == '__main__':
    process_link_relationships('scene3.config', 'scene3.nodes', 'link_relationships.txt')
    print("Results written to link_relationships.txt")
