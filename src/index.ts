import dotenv from "dotenv";
import { startBot } from "./bot.js";

dotenv.config();

const token = process.env.TELEGRAM_TOKEN;
if (!token) {
  throw new Error("TELEGRAM_TOKEN is not set in .env");
}

startBot(token).catch((error) => {
  console.error("Failed to start bot:", error);
  process.exit(1);
});
