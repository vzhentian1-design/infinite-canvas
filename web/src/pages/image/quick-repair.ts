export type QuickRepairOption = "remove-white-border" | "fix-chinese-text";

export const REMOVE_WHITE_BORDER_PROMPT =
    "保持这张图原有内容、文字、图片、布局和3:4比例不变，只修改最外层背景。把四周纯白背景替换成与当前画面主题色一致的浅色背景，从现有标题、图标或主视觉颜色中取色，并加入非常轻微的渐变、纹理或虚化，让边缘自然融入画面。中间的信息区可以继续保留白色或浅色卡片，但最外面一圈不要是纯白色。不要加生硬描边，不要给每个模块单独加框，不要改文字，不要改图片内容，不要重新排版，不要裁切主体。";

export const FIX_CHINESE_TEXT_PROMPT =
    "保持原图主体、图片元素、配色、布局和3:4比例不变，只修复文字区域。修正明显的错别字、乱码、伪文字、异常字符、变形或不可读文字，使其成为清晰自然、可读且语义正确的中文。若用户补充说明明确给出了需要替换成的目标文字，则以用户给出的目标文字为最高优先级；未明确指定的正常文字不要随意改写，不新增无关文案，不重新排版，不改主体图片。";

export const QUICK_REPAIR_PROTECTION = "除明确指定修改外，其他正常内容、构图、图片和排版尽量保持不变。";

export function composeQuickRepairPrompt(options: QuickRepairOption[], supplement: string) {
    const selected = new Set(options);
    const repairs = [
        selected.has("remove-white-border") ? `去白边：${REMOVE_WHITE_BORDER_PROMPT}` : "",
        selected.has("fix-chinese-text") ? `修乱码 / 错字：${FIX_CHINESE_TEXT_PROMPT}` : "",
    ].filter(Boolean);
    const extra = supplement.trim();
    if (!repairs.length) return extra;

    const prompt = repairs.length === 1 ? repairs[0]!.replace(/^[^：]+：/, "") : `仅执行以下返修：\n${repairs.map((repair, index) => `${index + 1}. ${repair}`).join("\n")}`;
    return [prompt, repairs.length > 1 ? `总保护约束：${QUICK_REPAIR_PROTECTION}` : "", extra ? `用户补充修改（最高优先级）：${extra}` : ""].filter(Boolean).join("\n\n");
}
