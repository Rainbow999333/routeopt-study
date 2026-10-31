# 重庆南岸道路实验数据

24 个公共道路节点 + 1 个模拟仓库。节点按地理分散程度选择，选择发生在优化之前；需求以固定种子 20261101 模拟生成。**这些不是客户订单，不代表真实企业运营。**

- 来源：OpenStreetMap，经 Overpass API 一次有界提取。
- 查询范围：南侧纬度 29.49、西侧经度 106.535、北侧纬度 29.56、东侧经度 106.625；字段顺序为 south, west, north, east。
- 数据时间：2026-10-31T18:51:02Z，即北京时间 2026-11-01 02:51:02。
- 提取文件：source/nanan-2026-11-01.osm，已去除贡献者用户名、用户 ID 和 changeset ID。
- SHA-256：256584317e5df26c61fe12914ab4daf2624deed8f73c2aeb59068fe48e218421。
- 构建：OSRM 26.10.0-amd64-debian，car.lua，MLD，固定镜像摘要见 tools/build_osrm_linux.py。
- 625 个含对角线的有向矩阵元素均可达，300 个无序点对中 296 个方向距离相差超过 1 米。
- 84 条实际使用弧的道路几何与矩阵里程逐一核对，最大差异为 0 米（接口精度）。

matrix.json 包含沿静态最快路径的距离和时间，不是实时交通，也不是已证明的全路网最短路径矩阵。局部提取范围可能影响可用绕行，未验证货车限高、所有实际限行或真实车辆配送。需求、车辆参数和仓库用途均为模拟。

道路数据、矩阵及适用的派生数据库遵守 ODbL-1.0，与代码 MIT 许可分开。署名：© OpenStreetMap contributors。

- https://www.openstreetmap.org/copyright
- https://opendatacommons.org/licenses/odbl/1-0/

复现：使用 source/ 中已保存的提取文件，不必再次访问 Overpass。Linux/Docker 运行 build_osrm_linux.py，启动 OSRM 时用与构建相同的 UID/GID，并仅监听本机，然后运行 make_chongqing_snapshot.py。源查询和原始/保存文件哈希见 source/*.meta.json，选择与质量记录见 quality.json。
