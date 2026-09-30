export const locales = ["pt-BR", "en", "zh-CN", "ar"] as const;
export type Locale = (typeof locales)[number];

export const localeLabels: Record<Locale, string> = {
  "pt-BR": "🇧🇷 Português",
  en: "🇺🇸 English",
  "zh-CN": "🇨🇳 简体中文",
  ar: "🌐 العربية الفصحى",
};

// Keep the accessible language name separate from its visual flag treatment.
// Some Windows controls render regional-indicator emoji as "BR", "US" or "CN".
export const localeNames: Record<Locale, string> = {
  "pt-BR": "Português",
  en: "English",
  "zh-CN": "简体中文",
  ar: "العربية الفصحى",
};

// This visual roster is intentionally language-neutral and is shared by every locale.
// Thirteen items per row keep the full roster legible on the arena landing page.
export const animalShowcaseRows = [
  ["🦅", "🐼", "🦘", "🦦", "🐵", "🐓", "🐂", "🐯", "🐘", "🐻", "🐙", "🦍", "🐎"],
  ["🦙", "🦌", "🐪", "🐐", "🦎", "🐱", "🦓", "🦜", "🐦", "🦁", "🐧", "🐟", "🦈"],
] as const;

export const animalNames: Record<Locale, Record<string, string>> = {
  "pt-BR": { eagle:"Águia", panda:"Panda", kangaroo:"Canguru", otter:"Lontra", monkey:"Macaco japonês", rooster:"Galo", bull:"Touro", tiger:"Tigre", elephant:"Elefante", bear:"Urso", octopus:"Polvo do Ártico", llama:"Lhama", white_tailed_deer:"Veado-de-cauda-branca", camel:"Camelo", goat:"Cabra", lizard:"Dragão de Komodo", angora_cat:"Gato angorá", zebra:"Zebra", macaw:"Arara", crane:"Grou-coroado", lion:"Leão", penguin:"Pinguim", gorilla:"Gorila", hilsa:"Hilsa", horse:"Cavalo", shark:"Tubarão" },
  en: { eagle:"Eagle", panda:"Panda", kangaroo:"Kangaroo", otter:"Otter", monkey:"Japanese macaque", rooster:"Rooster", bull:"Bull", tiger:"Tiger", elephant:"Elephant", bear:"Bear", octopus:"Arctic octopus", llama:"Llama", white_tailed_deer:"White-tailed deer", camel:"Camel", goat:"Goat", lizard:"Komodo dragon", angora_cat:"Turkish Angora", zebra:"Zebra", macaw:"Macaw", crane:"Crowned crane", lion:"Lion", penguin:"Penguin", gorilla:"Gorilla", hilsa:"Hilsa", horse:"Horse", shark:"Shark" },
  "zh-CN": { eagle:"鹰", panda:"熊猫", kangaroo:"袋鼠", otter:"水獭", monkey:"日本猕猴", rooster:"公鸡", bull:"公牛", tiger:"老虎", elephant:"大象", bear:"熊", octopus:"北极章鱼", llama:"羊驼", white_tailed_deer:"白尾鹿", camel:"骆驼", goat:"山羊", lizard:"科莫多巨蜥", angora_cat:"土耳其安哥拉猫", zebra:"斑马", macaw:"金刚鹦鹉", crane:"冠鹤", lion:"狮子", penguin:"企鹅", gorilla:"大猩猩", hilsa:"希尔萨鱼", horse:"马", shark:"鲨鱼" },
  ar: { eagle:"نسر", panda:"باندا", kangaroo:"كنغر", otter:"قضاعة", monkey:"مكاك ياباني", rooster:"ديك", bull:"ثور", tiger:"نمر", elephant:"فيل", bear:"دب", octopus:"أخطبوط القطب الشمالي", llama:"لاما", white_tailed_deer:"أيل أبيض الذيل", camel:"جمل", goat:"ماعز", lizard:"تنين كومودو", angora_cat:"قط أنغورا", zebra:"حمار وحشي", macaw:"ببغاء المكاو", crane:"كركي متوج", lion:"أسد", penguin:"بطريق", gorilla:"غوريلا", hilsa:"سمك هيلسا", horse:"حصان", shark:"قرش" },
};

export const interfaceText: Record<Locale, Record<string, string>> = {
  "pt-BR": { liveArena:"ARENA RPS AO VIVO", language:"Idioma", sponsorImage:"Espaço para imagem da marca patrocinadora", sponsorMessage:"Quero patrocinar o RPS", bestOf1:"Melhor de 1", bestOf3:"Melhor de 3", bestOf5:"Melhor de 5", rock:"Pedra", paper:"Papel", scissors:"Tesoura", player:"Jogador", challenger:"Desafiante", versus:"VS", readySuffix:"está pronto", worldMap:"Mapa-múndi dos animais", mapHint:"Deslize pelo mapa para explorar os países.", mapEnlarge:"Ampliar mapa", mapReduce:"Reduzir mapa", northAmerica:"América do Norte", southAmerica:"América do Sul", europe:"Europa", africa:"África", asia:"Ásia", oceania:"Oceania", antarctica:"Antártida", atlanticOcean:"Oceano Atlântico", arcticOcean:"Oceano Ártico" },
  en: { liveArena:"LIVE RPS ARENA", language:"Language", sponsorImage:"Sponsor brand image area", sponsorMessage:"I want to sponsor RPS", bestOf1:"Best of 1", bestOf3:"Best of 3", bestOf5:"Best of 5", rock:"Rock", paper:"Paper", scissors:"Scissors", player:"Player", challenger:"Challenger", versus:"VS", readySuffix:"is ready", worldMap:"Animal world map", mapHint:"Scroll the map to explore countries.", mapEnlarge:"Enlarge map", mapReduce:"Reduce map", northAmerica:"North America", southAmerica:"South America", europe:"Europe", africa:"Africa", asia:"Asia", oceania:"Oceania", antarctica:"Antarctica", atlanticOcean:"Atlantic Ocean", arcticOcean:"Arctic Ocean" },
  "zh-CN": { liveArena:"RPS 直播竞技场", language:"语言", sponsorImage:"赞助商品牌图片区域", sponsorMessage:"我想赞助 RPS", bestOf1:"一局定胜负", bestOf3:"三局两胜", bestOf5:"五局三胜", rock:"石头", paper:"布", scissors:"剪刀", player:"玩家", challenger:"挑战者", versus:"对阵", readySuffix:"已准备就绪", worldMap:"动物世界地图", mapHint:"滑动地图查看各个国家。", mapEnlarge:"放大地图", mapReduce:"缩小地图", northAmerica:"北美洲", southAmerica:"南美洲", europe:"欧洲", africa:"非洲", asia:"亚洲", oceania:"大洋洲", antarctica:"南极洲", atlanticOcean:"大西洋", arcticOcean:"北冰洋" },
  ar: { liveArena:"ساحة RPS المباشرة", language:"اللغة", sponsorImage:"مساحة لصورة العلامة التجارية للراعي", sponsorMessage:"أريد رعاية RPS", bestOf1:"الأفضل من جولة واحدة", bestOf3:"الأفضل من ثلاث جولات", bestOf5:"الأفضل من خمس جولات", rock:"حجر", paper:"ورق", scissors:"مقص", player:"لاعب", challenger:"المتحدي", versus:"ضد", readySuffix:"جاهز", worldMap:"خريطة عالم الحيوانات", mapHint:"مرر الخريطة لاستكشاف البلدان.", mapEnlarge:"تكبير الخريطة", mapReduce:"تصغير الخريطة", northAmerica:"أمريكا الشمالية", southAmerica:"أمريكا الجنوبية", europe:"أوروبا", africa:"أفريقيا", asia:"آسيا", oceania:"أوقيانوسيا", antarctica:"القارة القطبية الجنوبية", atlanticOcean:"المحيط الأطلسي", arcticOcean:"المحيط المتجمد الشمالي" },
};

export function animalName(locale: Locale, animal: string): string { return animalNames[locale][animal] ?? animal; }
export function uiText(locale: Locale, key: string): string { return interfaceText[locale][key] ?? key; }
const specialRegions: Record<Locale, Record<string, string>> = {
  "pt-BR": { arctic:"Ártico", southPole:"Polo Sul" },
  en: { arctic:"Arctic", southPole:"South Pole" },
  "zh-CN": { arctic:"北极地区", southPole:"南极" },
  ar: { arctic:"منطقة القطب الشمالي", southPole:"القطب الجنوبي" },
};
export function regionName(locale: Locale, region: string): string {
  return specialRegions[locale][region] ?? new Intl.DisplayNames([locale], { type: "region" }).of(region) ?? region;
}

const messages = {
  "pt-BR": { home:"Início", join:"Entrar no torneio", create:"Criar torneio", sponsor:"Quero patrocinar", sponsored:"Patrocinado por", tagline:"🦅 🐼 🦘 🦦 🐵 🐓 🐂 🐯 🐘 🐻 🐙 🦍 🐎 🦙 🦌 🐪 🐐 🦎 🐱 🦓 🦜 🐦 🦁 🐧 🐟 🦈", createTitle:"Monte a sua arena", joinTitle:"Entre na arena", capacity:"Capacidade máxima", format:"Formato", continue:"Continuar", name:"Seu nome", code:"Código do torneio", animal:"Escolha seu animal", strategy:"Estratégia", ready:"Estou pronto", waiting:"Aguardando o organizador", organizer:"Painel do organizador", start:"INICIAR TORNEIO", participants:"Participantes", training:"Treino", arena:"Arena ao vivo", events:"Eventos", bracket:"Chaveamento", save:"Salvar estratégia", total:"Pedra + Papel + Tesoura =", invalid:"A distribuição deve somar 100%.", network:"Não foi possível concluir a ação. Verifique o código ou a conexão.", started:"Torneio iniciado pelo servidor.", rules:"Melhor de", sound:"Efeitos sonoros", music:"Música", movement:"Velocidade de movimento", countdown:"Velocidade da contagem" },
  en: { home:"Home", join:"Join tournament", create:"Create tournament", sponsor:"Become a sponsor", sponsored:"Sponsored by", tagline:"🦅 🐼 🦘 🦦 🐵 🐓 🐂 🐯 🐘 🐻 🐙 🦍 🐎 🦙 🦌 🐪 🐐 🦎 🐱 🦓 🦜 🐦 🦁 🐧 🐟 🦈", createTitle:"Build your arena", joinTitle:"Enter the arena", capacity:"Maximum capacity", format:"Format", continue:"Continue", name:"Your name", code:"Tournament code", animal:"Choose your animal", strategy:"Strategy", ready:"I am ready", waiting:"Waiting for organizer", organizer:"Organizer dashboard", start:"START TOURNAMENT", participants:"Participants", training:"Training", arena:"Live arena", events:"Events", bracket:"Bracket", save:"Save strategy", total:"Rock + Paper + Scissors =", invalid:"Each distribution must total 100%.", network:"We could not complete that action. Check the code or connection.", started:"Tournament started by the server.", rules:"Best of", sound:"Sound effects", music:"Music", movement:"Movement speed", countdown:"Countdown speed" },
  "zh-CN": { home:"首页", join:"加入锦标赛", create:"创建锦标赛", sponsor:"成为赞助商", sponsored:"赞助商", tagline:"🦅 🐼 🦘 🦦 🐵 🐓 🐂 🐯 🐘 🐻 🐙 🦍 🐎 🦙 🦌 🐪 🐐 🦎 🐱 🦓 🦜 🐦 🦁 🐧 🐟 🦈", createTitle:"创建你的竞技场", joinTitle:"进入竞技场", capacity:"最大容量", format:"赛制", continue:"继续", name:"你的名字", code:"锦标赛代码", animal:"选择动物", strategy:"策略", ready:"准备好了", waiting:"等待组织者", organizer:"组织者面板", start:"开始锦标赛", participants:"参与者", training:"训练", arena:"实时竞技场", events:"事件", bracket:"对阵表", save:"保存策略", total:"石头 + 布 + 剪刀 =", invalid:"每个分布必须合计为 100%。", network:"无法完成操作。请检查代码或网络。", started:"锦标赛已由服务器开始。", rules:"三局两胜", sound:"音效", music:"音乐", movement:"移动速度", countdown:"倒计时速度" },
  ar: { home:"الرئيسية", join:"انضم إلى البطولة", create:"إنشاء بطولة", sponsor:"كن راعياً", sponsored:"برعاية", tagline:"🦅 🐼 🦘 🦦 🐵 🐓 🐂 🐯 🐘 🐻 🐙 🦍 🐎 🦙 🦌 🐪 🐐 🦎 🐱 🦓 🦜 🐦 🦁 🐧 🐟 🦈", createTitle:"أنشئ ساحتك", joinTitle:"ادخل إلى الساحة", capacity:"السعة القصوى", format:"النظام", continue:"متابعة", name:"اسمك", code:"رمز البطولة", animal:"اختر حيوانك", strategy:"الاستراتيجية", ready:"أنا جاهز", waiting:"بانتظار المنظم", organizer:"لوحة المنظم", start:"ابدأ البطولة", participants:"المشاركون", training:"تدريب", arena:"الساحة المباشرة", events:"الأحداث", bracket:"المواجهات", save:"حفظ الاستراتيجية", total:"حجر + ورق + مقص =", invalid:"يجب أن يساوي مجموع التوزيع 100٪.", network:"تعذر إكمال الإجراء. تحقق من الرمز أو الاتصال.", started:"بدأت البطولة من قبل الخادم.", rules:"الأفضل من", sound:"المؤثرات الصوتية", music:"الموسيقى", movement:"سرعة الحركة", countdown:"سرعة العد التنازلي" }
} as const;
export type MessageKey = keyof (typeof messages)["pt-BR"];
export function text(locale: Locale, key: MessageKey): string { return messages[locale][key]; }
