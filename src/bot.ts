import { Telegraf } from "telegraf";

export async function startBot(token: string) {
  const bot = new Telegraf(token);

  bot.start((ctx) => ctx.reply("Привет! Я бот для аналитики кофейни."));
  bot.help((ctx) => ctx.reply("Отправь /report чтобы получить отчёт по продажам."));

  bot.command("report", (ctx) => {
    ctx.reply("Здесь будет ежедневный отчёт по выручке, среднему чеку и прибыли.");
  });

  await bot.launch();
  console.log("Bot started");

  process.once("SIGINT", () => bot.stop("SIGINT"));
  process.once("SIGTERM", () => bot.stop("SIGTERM"));
}
