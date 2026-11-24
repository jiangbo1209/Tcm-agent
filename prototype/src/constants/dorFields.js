// AUTO-GENERATED from requirements/文献库母版（精简后）.xlsx
// 文献库 65 列 / 病案库 41 列，分组与必填/下拉均与 Excel 一致
export const LIT_GROUPS = [
  {
    "label": "现代文献基本信息",
    "fields": [
      {
        "key": "lit_1",
        "label": "题名",
        "desc": "文献标题原文",
        "required": true
      },
      {
        "key": "lit_2",
        "label": "作者",
        "desc": "第一作者及通讯作者",
        "required": true
      },
      {
        "key": "lit_3",
        "label": "发表年份",
        "desc": "数字（年）",
        "required": true
      },
      {
        "key": "lit_4",
        "label": "研究类型",
        "desc": "下拉选择；综述/未标注写实际类型",
        "required": true,
        "options": [
          "META分析/系统评价",
          "随机对照试验(RCT)",
          "队列研究",
          "病例对照研究",
          "横断面研究",
          "个案报道/病例系列",
          "准实验/前后对照",
          "综述",
          "其他"
        ]
      },
      {
        "key": "lit_5",
        "label": "质量/偏倚评估",
        "desc": "低/中/高风险",
        "required": false
      }
    ]
  },
  {
    "label": "研究对象",
    "fields": [
      {
        "key": "lit_6",
        "label": "年龄",
        "desc": "范围或均值±SD（岁）",
        "required": true
      },
      {
        "key": "lit_7",
        "label": "DOR诊断标准",
        "desc": "下拉选择诊断标准",
        "required": true,
        "options": [
          "2016中国卵巢储备功能减退专家共识",
          "博洛尼亚(Bologna)标准",
          "POSEIDON标准",
          "中华医学会生殖医学分会建议",
          "未明确说明",
          "其他"
        ]
      },
      {
        "key": "lit_8",
        "label": "诊断阈值依据",
        "desc": "AMH/AFC/基础FSH具体阈值（如AMH<1.1ng/mL）",
        "required": true
      },
      {
        "key": "lit_9",
        "label": "基线卵巢储备指标",
        "desc": "AMH、AFC、基础FSH数值+单位",
        "required": true
      },
      {
        "key": "lit_10",
        "label": "不孕类型",
        "desc": "下拉：原发/继发",
        "required": true,
        "options": [
          "原发性不孕",
          "继发性不孕",
          "未明确"
        ]
      },
      {
        "key": "lit_11",
        "label": "不孕年限",
        "desc": "年（数字）",
        "required": true
      },
      {
        "key": "lit_12",
        "label": "是否辅助生殖人群",
        "desc": "下拉：是/否",
        "required": true,
        "options": [
          "是",
          "否"
        ]
      },
      {
        "key": "lit_13",
        "label": "纳入标准",
        "desc": "简述",
        "required": false
      },
      {
        "key": "lit_14",
        "label": "排除标准",
        "desc": "简述",
        "required": false
      }
    ]
  },
  {
    "label": "中医证型",
    "fields": [
      {
        "key": "lit_15",
        "label": "证型名称",
        "desc": "下拉选择",
        "required": true,
        "options": [
          "肾虚证",
          "肝肾阴虚证",
          "脾肾阳虚证",
          "肝郁气滞证",
          "血瘀证",
          "气血两虚证",
          "痰湿证",
          "肾虚肝郁证",
          "肾虚血瘀证",
          "复合证型",
          "其他"
        ]
      },
      {
        "key": "lit_16",
        "label": "诊断依据",
        "desc": "主症/次症/舌脉",
        "required": true
      },
      {
        "key": "lit_17",
        "label": "治则治法",
        "desc": "如补肾填精、疏肝理气、活血化瘀",
        "required": true
      }
    ]
  },
  {
    "label": "中医治疗方案",
    "fields": [
      {
        "key": "lit_18",
        "label": "干预类型",
        "desc": "下拉选择",
        "required": true,
        "options": [
          "中药内服",
          "针灸",
          "电针",
          "艾灸",
          "埋线",
          "穴位贴敷",
          "耳穴压豆",
          "中药+针灸",
          "中西医结合",
          "推拿",
          "其他"
        ]
      },
      {
        "key": "lit_19",
        "label": "干预具体名称",
        "desc": "方剂名/治法名",
        "required": true
      },
      {
        "key": "lit_20",
        "label": "组成药物（含剂量）",
        "desc": "药名+克数",
        "required": true
      },
      {
        "key": "lit_21",
        "label": "疗程",
        "desc": "周/月/周期",
        "required": true
      },
      {
        "key": "lit_22",
        "label": "服用/操作方法",
        "desc": "频次、给药途径",
        "required": true
      },
      {
        "key": "lit_23",
        "label": "具体穴位",
        "desc": "针灸选穴",
        "required": false
      },
      {
        "key": "lit_24",
        "label": "治疗时机",
        "desc": "下拉选择",
        "required": false,
        "options": [
          "孕前调理",
          "周期调理",
          "促排前",
          "促排期",
          "移植前后",
          "黄体支持期",
          "全程"
        ]
      },
      {
        "key": "lit_25",
        "label": "对照组干预",
        "desc": "RCT对照设置",
        "required": false
      }
    ]
  },
  {
    "label": "西医治疗方案",
    "fields": [
      {
        "key": "lit_26",
        "label": "西药名称",
        "desc": "药名",
        "required": true
      },
      {
        "key": "lit_27",
        "label": "剂量",
        "desc": "单位",
        "required": true
      },
      {
        "key": "lit_28",
        "label": "疗程",
        "desc": "天/周期",
        "required": true
      },
      {
        "key": "lit_29",
        "label": "卵巢刺激/促排方案",
        "desc": "下拉选择",
        "required": true,
        "options": [
          "微刺激",
          "拮抗剂方案",
          "短方案",
          "长方案",
          "黄体期促排",
          "自然周期",
          "双刺激",
          "非降调节方案",
          "其他"
        ]
      },
      {
        "key": "lit_30",
        "label": "辅助用药",
        "desc": "DHEA/辅酶Q10/维生素D/GH等",
        "required": false
      },
      {
        "key": "lit_31",
        "label": "辅助生殖技术",
        "desc": "IVF/ICSI/冻胚移植/未行ART",
        "required": false
      },
      {
        "key": "lit_32",
        "label": "辅助生殖阶段干预",
        "desc": "描述",
        "required": false
      }
    ]
  },
  {
    "label": "疗效指标",
    "fields": [
      {
        "key": "lit_33",
        "label": "AMH(治疗前后)",
        "desc": "ng/mL",
        "required": true
      },
      {
        "key": "lit_34",
        "label": "AMH(治疗后)",
        "desc": "ng/mL",
        "required": true
      },
      {
        "key": "lit_35",
        "label": "FSH(治疗前)",
        "desc": "IU/L",
        "required": true
      },
      {
        "key": "lit_36",
        "label": "FSH(治疗后)",
        "desc": "IU/L",
        "required": true
      },
      {
        "key": "lit_37",
        "label": "LH",
        "desc": "IU/L",
        "required": false
      },
      {
        "key": "lit_38",
        "label": "E2",
        "desc": "pg/mL",
        "required": false
      },
      {
        "key": "lit_39",
        "label": "AFC(治疗前)",
        "desc": "个",
        "required": true
      },
      {
        "key": "lit_40",
        "label": "AFC(治疗后)",
        "desc": "个",
        "required": true
      },
      {
        "key": "lit_41",
        "label": "抑制素B(INHB)",
        "desc": "pg/mL",
        "required": false
      },
      {
        "key": "lit_42",
        "label": "月经情况",
        "desc": "周期天数/经量改善",
        "required": false
      },
      {
        "key": "lit_43",
        "label": "中医证候积分",
        "desc": "治疗前后积分",
        "required": false
      },
      {
        "key": "lit_44",
        "label": "生化妊娠率",
        "desc": "%",
        "required": false
      },
      {
        "key": "lit_45",
        "label": "临床妊娠率",
        "desc": "%",
        "required": true
      },
      {
        "key": "lit_46",
        "label": "持续妊娠率",
        "desc": "%",
        "required": false
      },
      {
        "key": "lit_47",
        "label": "流产率",
        "desc": "%",
        "required": false
      },
      {
        "key": "lit_48",
        "label": "活产率",
        "desc": "%",
        "required": true
      },
      {
        "key": "lit_49",
        "label": "其他疗效",
        "desc": "描述",
        "required": false
      }
    ]
  },
  {
    "label": "辅助生殖相关指标",
    "fields": [
      {
        "key": "lit_50",
        "label": "促排卵相关",
        "desc": "Gn用量",
        "required": false
      },
      {
        "key": "lit_51",
        "label": "辅助生殖相关指标-51",
        "desc": "Gn天数",
        "required": false
      },
      {
        "key": "lit_52",
        "label": "辅助生殖相关指标-52",
        "desc": "获卵数",
        "required": false
      },
      {
        "key": "lit_53",
        "label": "辅助生殖相关指标-53",
        "desc": "MII卵数",
        "required": false
      },
      {
        "key": "lit_54",
        "label": "辅助生殖相关指标-54",
        "desc": "成熟卵率",
        "required": false
      },
      {
        "key": "lit_55",
        "label": "胚胎发育与移植",
        "desc": "受精率",
        "required": false
      },
      {
        "key": "lit_56",
        "label": "辅助生殖相关指标-56",
        "desc": "优质胚胎率",
        "required": false
      },
      {
        "key": "lit_57",
        "label": "辅助生殖相关指标-57",
        "desc": "囊胚形成率",
        "required": false
      },
      {
        "key": "lit_58",
        "label": "辅助生殖相关指标-58",
        "desc": "移植胚胎数",
        "required": false
      },
      {
        "key": "lit_59",
        "label": "辅助生殖相关指标-59",
        "desc": "种植率",
        "required": false
      },
      {
        "key": "lit_60",
        "label": "妊娠结局相关",
        "desc": "临床妊娠率(ART)",
        "required": false
      },
      {
        "key": "lit_61",
        "label": "辅助生殖相关指标-61",
        "desc": "持续妊娠率(ART)",
        "required": false
      },
      {
        "key": "lit_62",
        "label": "辅助生殖相关指标-62",
        "desc": "活产率(ART)",
        "required": false
      },
      {
        "key": "lit_63",
        "label": "辅助生殖相关指标-63",
        "desc": "其他",
        "required": false
      }
    ]
  },
  {
    "label": "安全性信息",
    "fields": [
      {
        "key": "lit_64",
        "label": "不良反应",
        "desc": "（有，即描述）",
        "required": false
      },
      {
        "key": "lit_65",
        "label": "安全性评估（肝肾功能/心电图/三大常规等）",
        "desc": "（有，即描述）",
        "required": false
      }
    ]
  }
];

export const CASE_GROUPS = [
  {
    "label": "患者基本资料",
    "fields": [
      {
        "key": "case_1",
        "label": "年龄",
        "desc": "岁",
        "required": true
      },
      {
        "key": "case_2",
        "label": "BMI",
        "desc": "kg/m²",
        "required": false
      },
      {
        "key": "case_3",
        "label": "不孕年限",
        "desc": "年",
        "required": true
      },
      {
        "key": "case_4",
        "label": "不孕类型",
        "desc": "下拉：原发/继发",
        "required": true,
        "options": [
          "原发性不孕",
          "继发性不孕",
          "未明确"
        ]
      },
      {
        "key": "case_5",
        "label": "既往妊娠史",
        "desc": "次数/结局",
        "required": false
      },
      {
        "key": "case_6",
        "label": "既往治疗史",
        "desc": "中/西医治疗史",
        "required": false
      },
      {
        "key": "case_7",
        "label": "既往卵巢手术/放化疗史",
        "desc": "有/无+详情",
        "required": false
      },
      {
        "key": "case_8",
        "label": "家族史",
        "desc": "卵巢早衰/月经不调家族史",
        "required": false
      },
      {
        "key": "case_9",
        "label": "合并其他不孕因素",
        "desc": "男方/输卵管等",
        "required": false
      }
    ]
  },
  {
    "label": "DOR相关指标",
    "fields": [
      {
        "key": "case_10",
        "label": "AMH",
        "desc": "ng/mL",
        "required": true
      },
      {
        "key": "case_11",
        "label": "FSH",
        "desc": "IU/L",
        "required": true
      },
      {
        "key": "case_12",
        "label": "LH",
        "desc": "IU/L",
        "required": false
      },
      {
        "key": "case_13",
        "label": "E2",
        "desc": "pg/mL",
        "required": false
      },
      {
        "key": "case_14",
        "label": "AFC",
        "desc": "个",
        "required": true
      },
      {
        "key": "case_15",
        "label": "月经周期",
        "desc": "天",
        "required": true
      },
      {
        "key": "case_16",
        "label": "激素检测时相",
        "desc": "基础值/周期第X天",
        "required": false
      }
    ]
  },
  {
    "label": "中医四诊资料",
    "fields": [
      {
        "key": "case_17",
        "label": "主诉症状",
        "desc": "描述",
        "required": true
      },
      {
        "key": "case_18",
        "label": "舌象",
        "desc": "舌质/舌苔",
        "required": true
      },
      {
        "key": "case_19",
        "label": "脉象",
        "desc": "脉象描述",
        "required": true
      },
      {
        "key": "case_20",
        "label": "月经特征",
        "desc": "量/色/质/周期",
        "required": true
      },
      {
        "key": "case_21",
        "label": "情志睡眠",
        "desc": "描述",
        "required": false
      },
      {
        "key": "case_22",
        "label": "兼症",
        "desc": "腰酸/畏寒/头晕等",
        "required": false
      }
    ]
  },
  {
    "label": "临床证型分布",
    "fields": [
      {
        "key": "case_23",
        "label": "证型名称",
        "desc": "下拉选择",
        "required": true,
        "options": [
          "肾虚证",
          "肝肾阴虚证",
          "脾肾阳虚证",
          "肝郁气滞证",
          "血瘀证",
          "气血两虚证",
          "痰湿证",
          "肾虚肝郁证",
          "肾虚血瘀证",
          "复合证型",
          "其他"
        ]
      },
      {
        "key": "case_24",
        "label": "诊断依据",
        "desc": "描述",
        "required": true
      },
      {
        "key": "case_25",
        "label": "治则治法",
        "desc": "描述",
        "required": false
      }
    ]
  },
  {
    "label": "治疗方案",
    "fields": [
      {
        "key": "case_26",
        "label": "中医",
        "desc": "方药/针灸+剂量/穴位",
        "required": true
      },
      {
        "key": "case_27",
        "label": "中医治疗时机",
        "desc": "阶段（见下拉）",
        "required": false
      },
      {
        "key": "case_28",
        "label": "西医",
        "desc": "药物/促排方案",
        "required": true
      },
      {
        "key": "case_29",
        "label": "辅助生殖技术",
        "desc": "IVF/ICSI等",
        "required": false
      }
    ]
  },
  {
    "label": "治疗时序信息",
    "fields": [
      {
        "key": "case_30",
        "label": "治疗阶段",
        "desc": "下拉：孕前调理/促排前/促排期/取卵前后/移植前后/黄体支持期",
        "required": true,
        "options": [
          "孕前调理",
          "促排前",
          "促排期",
          "取卵前后",
          "移植前后",
          "黄体支持期"
        ]
      },
      {
        "key": "case_31",
        "label": "治疗周期数",
        "desc": "个周期",
        "required": true
      }
    ]
  },
  {
    "label": "临床结局",
    "fields": [
      {
        "key": "case_32",
        "label": "月经改善",
        "desc": "周期天数/经量前后对比",
        "required": true
      },
      {
        "key": "case_33",
        "label": "症状改善",
        "desc": "描述",
        "required": false
      },
      {
        "key": "case_34",
        "label": "激素改善",
        "desc": "AMH/FSH/E2前后值",
        "required": true
      },
      {
        "key": "case_35",
        "label": "AFC变化",
        "desc": "前后值",
        "required": true
      },
      {
        "key": "case_36",
        "label": "妊娠结局",
        "desc": "生化/临床/持续妊娠",
        "required": true
      },
      {
        "key": "case_37",
        "label": "流产结局",
        "desc": "有/无",
        "required": false
      },
      {
        "key": "case_38",
        "label": "活产结局",
        "desc": "有/无",
        "required": true
      },
      {
        "key": "case_39",
        "label": "随访时长",
        "desc": "月",
        "required": false
      }
    ]
  },
  {
    "label": "安全性结局",
    "fields": [
      {
        "key": "case_40",
        "label": "不良反应",
        "desc": "描述",
        "required": false
      },
      {
        "key": "case_41",
        "label": "异常实验室指标",
        "desc": "描述",
        "required": false
      }
    ]
  }
];

export const LIT_FIELD_COUNT = LIT_GROUPS.reduce((n, g) => n + g.fields.length, 0);
export const CASE_FIELD_COUNT = CASE_GROUPS.reduce((n, g) => n + g.fields.length, 0);

export function flattenGroups(groups) {
  return groups.flatMap((g) => g.fields.map((f) => ({ ...f, group: g.label })));
}