zs
=======

## Dependencies

`python>=3.6`

## Installation

```
pip install git+https://github.com/Linusp/zs.git
```

## Usage

### zs-tg

- fetch-msgs

  ```shell
  zs-tg fetch-msgs -n CHATNAME -d "2020-01-01" -l 100 -o messages.json
  ```

### zs-rss

- create-db
- fetch-wx-articles

  ```shell
  zs-rss fetch-wx-articles -n WECHAT_ARTICLES_CHANNEL -d 2020-04-01 -l 100
  ```

- add-wx-articles

  ```shell
  zs-rss add-wx-articles -i articles.json
  ```

  example content of `articles.json`:
  ```js
  {
      "http://mp.weixin.qq.com/s?__biz=MzIwMTc4ODE0Mw%3D%3D&mid=2247498353&idx=1&sn=19a6baac027018aeb76a688a9011cfde": {
          "name": "PaperWeekly",
          "title": "AI未来说 | 听大牛论自动驾驶领域干货，看无人驾驶小车真实运作",
          "desc": "第七期自动驾驶专场来了",
          "url": "http://mp.weixin.qq.com/s?__biz=MzIwMTc4ODE0Mw%3D%3D&mid=2247498353&idx=1&sn=19a6baac027018aeb76a688a9011cfde",
          "date": "2019-07-17 12:27:14+00:00",
          "sent": true
      },
      "http://mp.weixin.qq.com/s?__biz=MzIwMTc4ODE0Mw%3D%3D&mid=2247498353&idx=2&sn=caec95b9b57eac4cf1c6fa8cce99b4a6": {
          "name": "PaperWeekly",
          "title": "拿不到offer全额退款 | 编程测试与数据竞赛特训",
          "desc": "一站式解决找工作最大的两个问题：编程测试和项目经历",
          "url": "http://mp.weixin.qq.com/s?__biz=MzIwMTc4ODE0Mw%3D%3D&mid=2247498353&idx=2&sn=caec95b9b57eac4cf1c6fa8cce99b4a6",
          "date": "2019-07-17 12:27:15+00:00",
          "sent": true
      }
  }
  ```

- list-wx-articles

  ```shell
  zs-rss list-wx-articles -n 晚点LatePost --status unsent
  ```

  example output:
  ```
  [2020-04-01 12:10:49+00:00] 晚点LatePost -- 对话读者：晚点一周年，他们的留言让我们热泪盈眶
  [2020-04-02 20:28:01+00:00] 晚点LatePost -- BIGO：全球化夹缝中的生存冠军
  [2020-04-08 20:26:51+00:00] 晚点LatePost -- 晚点独家｜好未来披露员工销售造假始末
  [2020-04-10 17:49:41+00:00] 晚点LatePost -- 对话华裔科学家何大一：群体免疫不如全世界隔离封锁
  [2020-04-10 17:49:41+00:00] 晚点LatePost -- 腾讯希望借5G实现内外打通，从松散的联盟体向生态体过渡
  [2020-04-14 14:36:53+00:00] 晚点LatePost -- 晚点独家｜B站密集修补短板应对群雄围猎
  [2020-04-14 14:37:00+00:00] 晚点LatePost -- 快讯｜滴滴新成立用户增长部 冲刺“0188”战略目标
  ```

- send-wx-articles

  ```shell
  zs-rss send-wx-articles -n 晚点LatePost -l 100
  ```

- gen-wx-scenario

  ```shell
  zs-rss gen-wx-scenario -t kz -n 晚点LatePost -i postlate --kz-topic-id k69QJvO82RKoA -o postlate.json
  ```

  or
  ```shell
  zs-rss gen-wx-scenario -t efb -n 晚点LatePost -i postlate -o postlate.json
  ```

- gen-daily-scenario

  ```shell
  zs-rss gen-daily-scenario --feed-url "https://www.gcores.com/rss" -n 机核 -o gcore.json
  ```
