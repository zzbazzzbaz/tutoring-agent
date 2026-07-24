"""种子脚本：重建表 + 插入测试账号和项目。

用法：uv run python scripts/seed_users.py

会 DROP session/message/question/auth_token/user/project 表后重建。
插入：1 教师 + 2 学生 + 3 个计算机网络课程项目。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

from tutoring.auth.service import hash_password
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory
from tutoring.db import (
    models,  # noqa: F401 - register tables on metadata
    repos,
)

TABLES_TO_DROP = ["session", "message", "question", "auth_token", "user", "project"]

SEED_PROJECTS = [
    {
        "name": "校园网络规划与设计",
        "status": "published",
        "background_md": """# 校园网络规划与设计

## 项目背景

某新建高校占地约 500 亩，在校师生约 8000 人。校园分为教学楼（3 栋）、实验楼（1 栋）、
图书馆、行政楼、学生宿舍（6 栋）和教师公寓。现需要从零规划整个校园网络，使师生能够
在不同区域间无缝访问校内资源（教务系统、图书馆数据库、文件服务器）和互联网。

## 现有条件

- 已向运营商申请了一条 1Gbps 的教育网出口带宽
- 校内已铺设光纤主干，各楼宇间距离 100m～500m 不等
- 每栋楼宇内部已预埋六类网线到各个房间
- 采购预算充足，可自由选择交换机、路由器、防火墙等设备

## 需求描述

1. 教学楼共 60 间教室，每间需接入 2 台终端（教师机 + 投影）
2. 实验楼有 4 个机房，每个机房 60 台 PC，需访问外网且相互隔离
3. 图书馆需提供 200 个 Wi-Fi 接入点和 50 台查询终端
4. 学生宿舍每栋 200 间房，每间接入 4 个端口
5. 行政楼和教师公寓需要稳定的内网访问，且行政楼的数据需与教学区隔离
6. 所有区域需要统一的认证方式接入网络

## 需要思考的问题

- 如何划分 VLAN 和子网，才能兼顾隔离性与管理便捷性？
- 教学区、实验区、宿舍区、行政区之间的路由如何规划？
- DHCP、DNS 服务应该部署在哪里？是否需要冗余？
- 如何在出口处做 NAT 和访问控制，防止未授权外联？
- 无线网络的 SSID 和信道如何规划，避免干扰？""",
    },
    {
        "name": "家庭网络故障诊断与优化",
        "status": "published",
        "background_md": """# 家庭网络故障诊断与优化

## 项目背景

小李是一名远程办公的程序员，最近搬入新家后遇到了一系列网络问题。他的家庭网络由
一台运营商提供的光猫（集成路由功能）和一台自购的无线路由器组成。家里有以下设备：

- 1 台台式机（有线接入路由器）
- 1 台工作笔记本（Wi-Fi）
- 2 部手机（Wi-Fi）
- 1 台智能电视（Wi-Fi，看 4K 流媒体）
- 1 个智能家居网关（Wi-Fi，连接 20+ 个 IoT 设备）

## 故障现象

1. **间歇性断网**：笔记本每天会随机掉线 3～5 次，每次持续 10～30 秒后自动恢复
2. **网速不达标**：办理的是 500Mbps 宽带，台式机有线测速仅 90Mbps 左右
3. **视频卡顿**：智能电视看 4K 视频经常缓冲，尤其是在晚上 8～10 点
4. **IoT 设备离线**：智能家居设备偶尔集体掉线，需重启网关才能恢复
5. **DNS 异常**：有时浏览器打不开网页，但 ping IP 地址却通

## 现有网络信息

- 光猫 IP：192.168.1.1，开启 DHCP，地址池 192.168.1.100-200
- 路由器 IP：192.168.1.2（桥接模式），Wi-Fi 2.4GHz 单频段
- 所有设备都在同一个子网 192.168.1.0/24

## 需要思考的问题

- 间歇性断网可能的原因有哪些？如何逐一排查？
- 有线测速远低于带宽，瓶颈在哪个环节？是光猫、网线还是路由器？
- 4K 视频卡顿与 Wi-Fi 频段选择有什么关系？2.4GHz vs 5GHz 如何取舍？
- DNS 异常的根因是什么？如何配置更可靠的 DNS？
- 所有设备在同一子网是否合理？IoT 设备是否应该隔离？""",
    },
    {
        "name": "小型企业网络架构搭建",
        "status": "published",
        "background_md": """# 小型企业网络架构搭建

## 项目背景

一家 50 人的科技创业公司即将搬入新办公区（单层，约 800㎡）。公司有研发部（30 人）、
市场部（10 人）、行政财务（5 人）和管理层（5 人）。业务依赖一套内部 ERP 系统、
一个 Git 代码仓库和对外提供服务的 API 网关。公司希望搭建一套安全、可扩展的企业网络，
同时支持 10 名研发人员居家远程办公。

## 现有资源

- 运营商提供 500Mbps 企业宽带（含 1 个固定公网 IP）
- 已采购 1 台企业级防火墙、2 台三层交换机、3 台 PoE 交换机
- 有 3 台服务器（2 台运行内部服务，1 台做数据库）
- 已注册域名 example-tech.com

## 需求描述

1. 研发部需要访问 Git 仓库和内网开发环境，且代码不可泄露到外网
2. 市场部和行政财务只需访问互联网和 ERP 系统
3. 管理层需要专属网段，与其他部门隔离
4. 对外服务（API 网关）需要从公网可访问，但必须与内网隔离
5. 10 名远程研发人员需要通过 VPN 安全接入内网开发环境
6. 所有出入流量需要有日志审计，关键服务需做高可用

## 需要思考的问题

- 如何设计网络拓扑？DMZ 应该放在什么位置？
- 内部子网如何划分？部门间如何做访问控制（ACL）？
- VPN 应该选择哪种方案（IPSec / SSL VPN / WireGuard）？为什么？
- 对外服务的端口映射和反向代理如何规划？如何防御常见网络攻击？
- DHCP、DNS、NTP 等基础服务如何部署？单点故障如何避免？
- 如何监控网络健康状态？关键指标有哪些？""",
    },
]


async def main() -> None:
    engine: AsyncEngine = create_engine(settings.database_url)

    # 1. Drop old tables
    print("Dropping old tables...")
    async with engine.begin() as conn:
        for table in TABLES_TO_DROP:
            await conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        print("  done")

    # 2. Create all tables
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("  done")

    # 3. Insert seed users and projects
    session_factory = create_session_factory(engine)
    async with session_factory() as db:
        teacher = await repos.create_user(
            db,
            username="teacher1",
            password_hash=hash_password("teacher123"),
            role="teacher",
            name="测试教师",
        )
        print(f"  teacher: {teacher.username} / {teacher.id}")

        for i in range(1, 3):
            student = await repos.create_user(
                db,
                username=f"student{i}",
                password_hash=hash_password("student123"),
                role="student",
                name=f"测试学生{i}",
            )
            print(f"  student: {student.username} / {student.id}")

        for project_data in SEED_PROJECTS:
            project = await repos.create_project(db, **project_data)
            print(f"  project: {project.name} / {project.id}")

    await engine.dispose()
    print("\nSeed complete. Login:")
    print("  teacher: teacher1 / teacher123")
    print("  student: student1 / student123")


if __name__ == "__main__":
    asyncio.run(main())
