from django.urls import path
from . import views
from . import exata_integration
from .views import SocketView
from .views import trigger_push  # 导入 trigger_push 视图函数

urlpatterns = [
path('connect/', SocketView.as_view(), name='connect'),
    path('send/', SocketView.as_view(), name='send_message'),
    path('getToken', views.getToken, name='getToken'),
    path('getHandleMessage/', SocketView.as_view(), name='getHandleMessage'),
    path('start-simulation/', SocketView.as_view(), name='start_simulation'),  # 新增的路径，启动仿真
    path('pause-simulation/', SocketView.as_view(), name='pause_simulation'),  # 新增的路径，暂停仿真
    path('step-simulation/', SocketView.as_view(), name='step_simulation'),  # 新增的路径，暂停仿真
    path('continue-simulation/', SocketView.as_view(), name='continue_simulation'),  # 新增的路径，解除暂停仿真
    path('send-simulation-message/', SocketView.as_view(), name='send_simulation_message'),  # 新增的路径，按顺序发送消息
    path('trigger_push/', trigger_push, name='trigger_push'),  # 添加该路由
    path('stop-simulation/', SocketView.as_view(), name='stop_simulation'),  # 添加该路由

    path('api/addSceneList', views.add_scene_list, name='add_scene_list'),
    path('api/deleteSceneList/<int:scene_id>', views.delete_scene_list, name='delete_scene_list'),#name用来重定向，reverse()
    path('api/editSceneList/<int:scene_id>', views.edit_scene_list, name='edit_scene_list'),
    path('api/getSceneList', views.get_scene_list, name='get_scene_list'),
    path('api/addSubnetList', views.add_subnet_list, name='add_subnet_list'),
    path('api/getSubnetList', views.get_subnet_list, name='get_subnet_list'),
    path('api/deleteSubnetList/<int:subnet_id>', views.delete_subnet_list, name='delete_subnet_list'),
    path('api/editSubnetList/<int:subnet_id>', views.edit_subnet_list, name='edit_subnet_list'),
    path('api/calculateLeoViaPoints', views.calculate_leo_via_points, name='calculate_leo_via_points'),
    path('api/addNodeList', views.add_node_list, name='add_node_list'),
    path('api/getNodeList', views.get_node_list, name='get_node_list'),
    path('api/editNodeList/<int:node_id>', views.edit_node_list, name='edit_node_list'),
    path('api/deleteNodeList/<int:node_id>', views.delete_node_list, name='delete_node_list'),
    path('api/addConfigurationList', views.add_configuration_list, name='add_configuration_list'),
    path('api/getConfigurationList', views.get_configuration_list, name='get_configuration_list'),
    path('api/editConfigurationList/<int:configuration_id>', views.edit_configuration_list,
         name='edit_configuration_list'),
    path('api/deleteConfigurationList/<int:configuration_id>', views.delete_configuration_list, name='delete_configuration_list'),
    path('api/addLinkList', views.add_link_list, name='add_link_list'),
    path('api/getLinkList', views.get_link_list, name='get_link_list'),
    path('api/deleteLinkList/<int:link_id>', views.delete_link_list, name='delete_link_list'),
    path('api/editLinkList/<int:link_id>', views.edit_link_list, name='edit_link_list'),
    path('api/addNodeErrorList', views.add_node_error_list, name='add_node_error_list'),
    path('api/deleteNodeErrorList/<int:node_error_id>', views.delete_node_error_list, name='delete_node_error_list'),
    path('api/getNodeErrorList', views.get_node_error_list, name='get_node_error_list'),
    path('api/addLinkErrorList', views.add_link_error_list, name='add_link_error_list'),
    path('api/getLinkErrorList', views.get_link_error_list, name='get_link_error_list'),
    path('api/deleteLinkErrorList/<int:link_error_id>', views.delete_link_error_list, name='delete_link_error_list'),
    path('api/addNodeTemplateList', views.add_node_template_list, name='add_node_template_list'),
    path('api/getNodeTemplateList', views.get_node_template_list, name='get_node_template_list'),
    path('api/editNodeTemplateList/<int:node_template_id>', views.edit_node_template_list,
         name='edit_node_template_list'),
    path('api/deleteNodeTemplateList/<int:node_template_id>', views.delete_node_template_list,
         name='delete_node_template_list'),
    path('api/editLinkErrorList/<int:link_error_id>', views.edit_link_error_list, name='edit_link_error_list'),
    path('api/editNodeErrorList/<int:node_error_id>', views.edit_node_error_list, name='edit_node_error_list'),
    path('api/addNodeMapList', views.add_node_map_list, name='add_node_map_list'),
    path('api/getNodeMapList', views.get_node_interfaces, name='get_node_interfaces'),
    path('api/deleteNodeMapList/<int:mapping_id>', views.delete_node_map_list,
         name='delete_node_map_list'),
    path('api/editNodeMapList/<int:mapping_id>', views.edit_node_map_list, name='edit_node_map_list'),
    path('api/getMapList', views.get_map_list, name='get_map_list'),
    path('api/generateExataConfig', views.generate_exata_config, name='generate_exata_config'),
    path('api/generateLinkFile/', views.generate_link_file, name='generate_link_file'),
    path('api/generateOrbitFile/', views.generate_orbit_file, name='generate_orbit_file'),
    path('api/generateFaultFile/', views.generate_fault_file, name='generate_fault_file'),
    path('api/generateNodeFile/', views.generate_node_file, name='generate_node_file'),
    path('api/generateInitialFile/', views.generate_initial_file, name='generate_initial_file'),
    # path('api/generateappFile/', views.generate_scene_app, name='generate_scene_app'),
    # path('api/generatenodesFile/', views.generate_scene_nodes, name='generate_scene_nodes'),
    # path('api/generatefaultFile/', views.generate_scene_fault, name='generate_scene_fault'),
    # path('api/generatedisplayFile/', views.generate_display_file, name='generate_display_file'),
    path('api/download_all_files', views.download_all_files, name='download_all_files'),
    path('api/analysis', views.analysis_results, name='analysis-results'),
    path('api/get_scene_files/', views.get_scene_files, name='get_scene_files'),
    path('api/get_rx_power_log/', views.get_rx_power_log, name='get_rx_power_log'),
    path('api/get_ospf_detected/', views.get_ospf_detected, name='get_ospf_detected'),
    path('api/getPhysicalLayerData/', views.get_physical_layer_data, name='get_physical_layer_data'),
    path('api/getLinkLayerData/', views.get_link_layer_data, name='get_link_layer_data'),
    path('api/getNetworkLayerData/', views.get_network_layer_data, name='get_network_layer_data'),
    path('api/getNetworkLayerBlock/', views.get_network_layer_block, name='get_network_layer_block'),

    path('api/get_exata_scene_files', exata_integration.get_exata_scene_files, name='get_exata_scene_files_no_slash'),
    path('api/get_exata_scene_files/', exata_integration.get_exata_scene_files, name='get_exata_scene_files'),
    path('api/analyze_exata_stat', exata_integration.analyze_exata_stat, name='analyze_exata_stat_no_slash'),
    path('api/analyze_exata_stat/', exata_integration.analyze_exata_stat, name='analyze_exata_stat'),
    
    path('api/startSimulation/', views.start_simulation, name='start_simulation'),
    path('api/analyzeQueueData/', views.analyze_queue_data, name='analyze_queue_data'),
    path('api/analyzeStatsData/', views.get_slot_stats_data, name='get_slot_stats_data'),
    path('api/slotTable/', views.save_slot_table, name='save_slot_table'),
    path('api/getSlotTable', views.get_slot_table, name='get_slot_table'),
]
#每个url对应返回唯一的结果
#这是子应用中的url和视图函数对应，还需要把子应用注册到根url里
"""
RESTful 原则：URL 应该标识资源（名词），而不是操作（动词）。操作应该由 HTTP 方法（GET, POST, PUT, PATCH, DELETE）来表示。
"""
