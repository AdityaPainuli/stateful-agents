import Redis from "ioredis";
import "dotenv/config";


export const redis = new Redis({
  username: process.env.REDIS_USERNAME as string,
  password: process.env.REDIS_PASSWORD as string,
  port: Number(process.env.REDIS_PORT),
  host: process.env.REDIS_HOST as string,
});

