# app/utils.py
from api.models import Node
import json
def update_nodes_details(scene_id=23):
    """
    内置 JSON 数据，更新指定 scene_id 下节点 details 字段
    """
    json_data = {
    "1": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "PHY-ABSTRACT-DATA-RATE": "48000.000000",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {
                "MAC-SLOT-NODETYPE": "CLUSTER-HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-HEAD"
            },
            "Routing": {}
        }
    ],
    "2": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "3": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "4": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "5": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "6": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "PHY-ABSTRACT-DATA-RATE": "48000.000000",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {
                "MAC-SLOT-NODETYPE": "CLUSTER-HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "HEAD"
            },
            "Routing": {}
        }
    ],
    "7": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "8": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "9": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "10": [
        {
            "Physical": {
                "PHY-ABSTRACT-TX-POWER": "20",
                "PHY-ABSTRACT-DATA-RATE": "196000.000000",
                "ANTENNA-CABLE-LOSS": "0.0",
                "ANTENNA-EFFICIENCY": "0.8",
                "DUMMY-ANTENNA-MODEL-CONFIG-FILE-SPECIFY": "NO",
                "ANTENNA-HEIGHT": "1.5",
                "ANTENNA-ORIENTATION-ELEVATION": "0",
                "ANTENNA-MODEL": "OMNIDIRECTIONAL",
                "ANTENNA-CONNECTION-LOSS": "0.2",
                "ANTENNA-GAIN": "3",
                "ANTENNA-ORIENTATION-AZIMUTH": "0",
                "ANTENNA-MISMATCH-LOSS": "0.3",
                "ANTENNA-ORIENTATION-AZIMUTH-SPEED": "0.0",
                "ANTENNA-ORIENTATION-ROLL": "0"
            },
            "MAC": {},
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "11": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "12": [
        {
            "Physical": {
                "PHY-ABSTRACT-DATA-RATE": "16000000.000000"
            },
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-ZHONGSU"
            },
            "Routing": {}
        },
        {
            "Physical": {
                "PHY-ABSTRACT-DATA-RATE": "16000000.000000"
            },
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-ZHONGSU"
            },
            "Routing": {}
        }
    ],
    "13": [
        {
            "Physical": {
                "PHY-ABSTRACT-DATA-RATE": "16000000.000000"
            },
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-ZHONGSU"
            },
            "Routing": {}
        }
    ],
    "14": [
        {
            "Physical": {
                "PHY-ABSTRACT-DATA-RATE": "16000000.000000"
            },
            "MAC": {
                "FIXED-FRAME-LENGTH": "472",
                "MAC-SLOT-NODETYPE": "CLUSTER-ZHONGSU"
            },
            "Routing": {}
        }
    ],
    "15": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "16": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "17": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "18": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "19": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "20": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "21": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "22": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "23": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        },
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "24": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "25": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "26": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "27": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "28": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "29": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "34": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "35": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "36": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "37": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "42": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "43": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "46": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "47": [
        {
            "Physical": {},
            "MAC": {},
            "Routing": {
                "ROUTING-PROTOCOL-IPv4": "OSPFv2"
            }
        }
    ],
    "50": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ],
    "51": [
        {
            "Physical": {},
            "MAC": {
                "NODE-TYPE": "MEMBER"
            },
            "Routing": {}
        }
    ]
}


    # 假设 json_data 是你提供的第二个 JSON 字典
    for node_id, node_list in json_data.items():
        # 转换成第一种 details 格式：每个节点对象变成字符串
        details_formatted = [json.dumps(node) for node in node_list]

        try:
            node = Node.objects.get(sceneId=scene_id, nodeName=str(node_id))
            node.details = details_formatted  # 写入 details 字段
            node.save()
            print(f"Node {node_id} updated successfully.")
            print(f"{node.details}")
        except Node.DoesNotExist:
            print(f"Node {node_id} does not exist in scene {scene_id}.")

