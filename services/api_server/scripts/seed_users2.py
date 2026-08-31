"""种子脚本：重建表 + 插入测试账号和项目（普通心理学·学前教育方向）。

用法：uv run python scripts/seed_users2.py

会 DROP session/message/question/auth_token/user/project 表后重建。
插入：1 教师 + 2 学生 + 3 个普通心理学课程项目。
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
        "name": "幼儿入园适应中的心理观察与干预",
        "status": "published",
        "background_md": """# 幼儿入园适应中的心理观察与干预

## 项目背景

你是一名刚入职的幼儿园小班（3～4 岁）教师。新学期开学，班级迎来了 25 名新生，
多数孩子第一次离开家庭进入集体生活。入园两周以来，你观察到孩子们表现出不同的
适应状态，需要你运用普通心理学的知识读懂这些行为背后的心理机制，并设计贴合的
引导策略，帮助每个孩子平稳度过"入园焦虑期"。

## 观察现象

1. **情绪起伏**：部分孩子入园时哭闹不止、抱着家长不松手，午睡时也容易惊醒抽泣
2. **感知觉差异**：有的孩子对陌生环境声音、光线特别敏感，稍有响动就紧张；有的则反应迟缓
3. **注意难以集中**：集体活动时，多数孩子注意力只能维持几分钟，容易被窗外的声音、玩具吸引
4. **记忆表现**：有的孩子能记住老师讲的故事和儿歌，有的却"左耳进右耳出"，转头就忘
5. **分离差异**：性格差异明显，有的孩子很快融入集体，有的持续被动、不愿和同伴互动

## 需要思考的问题

- 分离焦虑背后的情绪与依恋机制是什么？如何依据情绪与情感的知识安抚孩子？
- 如何利用注意的稳定性与波动规律，设计更适合幼儿的集体活动节奏？
- 幼儿的记忆以什么类型为主？为什么有些孩子记不住？如何提升记忆效果？
- 不同气质类型（胆汁质、多血质、黏液质、抑郁质）在入园适应上如何表现？如何因材施教？
- 如何通过观察孩子的感知觉反应，判断其发育是否正常？""",
        "mainline": {
            "objective": "读懂幼儿入园适应行为背后的心理机制，并能为每个孩子设计贴合的引导策略，帮助其平稳度过入园焦虑期。",
            "stages": [
                {
                    "id": "stg_01",
                    "order": 1,
                    "title": "情绪与分离焦虑",
                    "guide": "先从哭闹、分离等表现切入，引导学生推导依恋与情绪机制，再讨论安抚策略。",
                    "student_desc": "了解孩子哭闹、黏人背后的情绪与依恋机制，学会安抚策略。",
                    "deliverable": {
                        "title": "焦虑行为观察记录",
                        "instructions": "记录并分析 3 个幼儿分离焦虑行为案例（现象、可能的心理机制、建议干预）。",
                    },
                },
                {
                    "id": "stg_02",
                    "order": 2,
                    "title": "注意的稳定性与活动设计",
                    "guide": "引导学生分析幼儿注意力短暂、易被干扰的现象，结合注意规律设计集体活动节奏。",
                    "student_desc": "理解幼儿注意力短暂、易分散的特点，学会设计合适的活动节奏。",
                    "deliverable": None,
                },
                {
                    "id": "stg_03",
                    "order": 3,
                    "title": "幼儿记忆特点与提升策略",
                    "guide": "引导学生区分幼儿记忆的主要类型，解释“左耳进右耳出”的原因并设计提升方法。",
                    "student_desc": "认识幼儿记忆的主要特点，掌握提升记忆效果的方法。",
                    "deliverable": None,
                },
                {
                    "id": "stg_04",
                    "order": 4,
                    "title": "气质类型与因材施教",
                    "guide": "引导学生用四种气质类型解读入园差异，并为不同气质幼儿设计个别化引导。",
                    "student_desc": "认识四种气质类型，学会为不同气质的孩子设计个别化引导。",
                    "deliverable": {
                        "title": "个别化引导方案",
                        "instructions": "针对一名“持续被动、不愿和同伴互动”的幼儿，结合气质理论设计渐进式引导方案。",
                    },
                },
                {
                    "id": "stg_05",
                    "order": 5,
                    "title": "感知觉观察与发育判断",
                    "guide": "引导学生通过观察幼儿感知觉反应判断其发育是否正常，并明确教师的能力边界。",
                    "student_desc": "学习通过观察感知觉反应，判断幼儿发育是否正常。",
                    "deliverable": None,
                },
            ],
        },
    },
    {
        "name": "幼儿游戏中的思维与想象发展支持",
        "status": "published",
        "background_md": """# 幼儿游戏中的思维与想象发展支持

## 项目背景

你是一名幼儿园中班（4～5 岁）教师，正在规划"角色游戏"区域。中班幼儿正处于
思维与想象快速发展的关键期，他们开始出现象征性游戏、创造性的角色扮演，会
"假装"自己是医生、妈妈、警察。你希望借助游戏这一载体，观察和评估幼儿的思维
与想象发展水平，并设计能促进其发展的游戏环境与引导策略。

## 现有条件

- 班级有积木区、娃娃家、阅读区、美工区、建构区等区域
- 每周有 3 次自由游戏时间，每次约 40 分钟
- 家长普遍反映孩子"爱幻想""爱问为什么"，但不知如何引导
- 部分幼儿游戏时停留在简单摆弄，难以进入深入的角色扮演

## 需要观察与思考的问题

1. 幼儿"假装"游戏体现了怎样的想象过程？再造想象与创造想象在游戏中如何区分？
2. 幼儿的思维以具体形象思维为主，这如何影响他们对游戏道具、情境的理解？
3. 如何通过提问和材料投放，促进幼儿从直观动作思维向具体形象思维发展？
4. 幼儿在游戏中"解决问题"时，其问题解决策略与成人有何不同？影响因素有哪些？
5. 创造力（发散思维）在游戏中如何表现？教师如何保护而不扼杀幼儿的创造性想象？

## 需要设计的引导

- 设计一个能激发想象的角色游戏主题，并说明材料与环境如何支持想象发展
- 针对一名"只肯摆弄积木、不愿参与角色扮演"的幼儿，设计渐进引导方案""",
        "mainline": {
            "objective": "借助角色游戏观察幼儿思维与想象的发展水平，并设计能促进其发展的游戏环境与引导策略。",
            "stages": [
                {
                    "id": "stg_01",
                    "order": 1,
                    "title": "象征性游戏与想象",
                    "guide": "从“假装”游戏现象切入，引导学生理解想象过程，区分再造想象与创造想象。",
                    "student_desc": "理解“假装”游戏背后的想象过程，区分再造想象与创造想象。",
                    "deliverable": None,
                },
                {
                    "id": "stg_02",
                    "order": 2,
                    "title": "具体形象思维与游戏理解",
                    "guide": "引导学生分析具体形象思维如何影响幼儿对游戏道具、情境的理解。",
                    "student_desc": "认识具体形象思维如何影响幼儿对游戏的理解。",
                    "deliverable": None,
                },
                {
                    "id": "stg_03",
                    "order": 3,
                    "title": "问题解决与思维发展",
                    "guide": "引导学生比较幼儿与成人问题解决策略的差异，讨论影响因素与促进方法。",
                    "student_desc": "了解幼儿在游戏中解决问题的方式及其特点。",
                    "deliverable": None,
                },
                {
                    "id": "stg_04",
                    "order": 4,
                    "title": "创造力与游戏引导",
                    "guide": "引导学生识别游戏中发散思维的表现，讨论教师如何保护而不扼杀创造性想象。",
                    "student_desc": "识别游戏中的创造力表现，学会设计激发想象的角色游戏。",
                    "deliverable": {
                        "title": "角色游戏主题设计方案",
                        "instructions": "设计一个能激发想象的角色游戏主题，说明材料与环境如何支持想象发展，并针对“只肯摆弄积木、不愿参与角色扮演”的幼儿给出渐进引导方案。",
                    },
                },
            ],
        },
    },
    {
        "name": "大班幼儿入学准备中的情绪与意志培养",
        "status": "published",
        "background_md": """# 大班幼儿入学准备中的情绪与意志培养

## 项目背景

你是一名幼儿园大班（5～6 岁）教师，孩子们明年即将升入小学。与中学和高校不同，
幼儿园"幼小衔接"的重点不是知识储备，而是心理准备。你发现大班幼儿即将面临
从"游戏为主"到"学习为主"的转变，需要帮助他们建立积极的入学期待、学会管理
情绪、增强坚持完成任务的自制力，为平稳过渡到小学做好心理准备。

## 观察现象

1. **情绪体验加深**：部分孩子开始在意"输赢""表扬"，对失败有较明显的沮丧情绪
2. **意志品质显现**：有的孩子能坚持完成较难的拼图或建构任务，有的遇到困难就想放弃
3. **动机萌芽**：孩子的活动兴趣开始分化，有些爱阅读、有些爱运动，内在动机各不相同
4. **性格轮廓形成**：能观察到孩子比较稳定的行为倾向，如胆大/胆小、主动/被动、合群/孤僻
5. **自我意识增强**：孩子开始在意同伴评价，渴望被认可，也容易产生嫉妒、攀比心理

## 需要思考的问题

- 如何帮助幼儿正确认识并表达情绪？教师如何运用情绪引导技巧？
- 幼儿的意志品质（自觉性、果断性、坚持性、自制性）如何培养？哪些任务适合锻炼？
- 如何利用幼儿的兴趣和内在动机，激发其主动学习与探索？
- 幼儿的性格特点如何形成？教师和家长如何正确认识和评价，而非随意贴标签？
- 面对"输不起""怕失败"的孩子，如何培养其抗挫折能力？

## 需要设计的方案

- 设计一套"入学准备"情绪与意志培养活动方案（含目标、活动、评价）
- 针对一名"遇难即退、缺乏坚持"的幼儿，结合气质与动机理论设计个别化指导""",
        "mainline": {
            "objective": "帮助大班幼儿做好入学心理准备：学会管理情绪、发展意志品质、激发内在动机、正确认识性格、增强抗挫折能力。",
            "stages": [
                {
                    "id": "stg_01",
                    "order": 1,
                    "title": "情绪认识与表达",
                    "guide": "引导学生讨论幼儿情绪体验加深的现象，设计情绪认识与表达的引导方法。",
                    "student_desc": "帮助幼儿认识并表达情绪，掌握情绪引导方法。",
                    "deliverable": None,
                },
                {
                    "id": "stg_02",
                    "order": 2,
                    "title": "意志品质培养",
                    "guide": "引导学生结合自觉性、果断性、坚持性、自制性，设计适合幼儿的锻炼任务。",
                    "student_desc": "了解意志品质的培养方法，设计适合幼儿的锻炼任务。",
                    "deliverable": None,
                },
                {
                    "id": "stg_03",
                    "order": 3,
                    "title": "兴趣与内在动机",
                    "guide": "引导学生分析幼儿活动兴趣分化现象，讨论如何利用内在动机激发主动学习与探索。",
                    "student_desc": "理解幼儿兴趣分化，学会激发其内在动机。",
                    "deliverable": None,
                },
                {
                    "id": "stg_04",
                    "order": 4,
                    "title": "性格认识与评价",
                    "guide": "引导学生认识幼儿性格的形成过程，讨论如何正确评价而非随意贴标签。",
                    "student_desc": "认识幼儿性格的形成，学会正确评价而非贴标签。",
                    "deliverable": None,
                },
                {
                    "id": "stg_05",
                    "order": 5,
                    "title": "抗挫折能力培养",
                    "guide": "引导学生针对“输不起、怕失败”的孩子，设计抗挫折能力培养策略。",
                    "student_desc": "学习培养幼儿抗挫折能力的方法与策略。",
                    "deliverable": {
                        "title": "入学准备情绪与意志培养活动方案",
                        "instructions": "设计一套涵盖情绪与意志培养的入学准备活动方案（含目标、活动、评价），并针对一名“遇难即退、缺乏坚持”的幼儿，结合气质与动机理论设计个别化指导。",
                    },
                },
            ],
        },
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