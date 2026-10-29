# わんコメ連動

いつもの `start-game.cmd` で、API・OBS連動・わんコメ受信・ゲームが起動します。
わんコメが未起動なら接続を待ち、起動後に自動接続します。二重起動はロックで防ぎます。
ゲーム本体の再ビルド・わんコメのプラグイン導入・Python追加パッケージは不要です。

接続設定: `Save/GiftAPI/onecomme.json`

初期接続先は `ws://127.0.0.1:11180/sub?p=connected,comments,meta,reactions,services`。
別のPCでわんコメを動かす場合やポートを変更している場合は、このURLを変更して
受信プログラムを起動し直してください。わんコメ側でもその接続元を許可してください。
一時停止する場合は `enabled` を `false` にします（再接続時に読み込み）。

## Version6-6の対応表

`Save/GiftAPI/gift-map.json` を編集すると次の受信から反映されます。

| サービス | ギフト | 単価 | 効果 |
| --- | --- | --- | --- |
| TikTok | バッド・マスター | 99コイン | CHALLENGE ATTACKに1単位 |
| TikTok | ボリュームアップ | 249コイン | SHIELDに1単位 |
| YouTube | マイク | 100ジュエル | CHALLENGE ATTACKに1単位 |
| YouTube | やる気満々 | 250ジュエル | SHIELDに1単位 |
| 両方 | その他の有料ギフト | 1コイン・ジュエル | RESCUE 1pt |

正式IDは実受信で未確認のため、`match_name` で構造化されたギフト名に照合します。
TikTokは `gift.details.giftName`、YouTubeは `giftName` またはギフトHTMLのテキスト
（末尾の「を送信しました」を除く）を使用します。通常コメントは照合しません。
ID確定後は、対応表のキーをTikTokのID／YouTubeの画像ファイル名に変更できます。
明示IDの割り当てが優先されます。単価だけではATTACK・SHIELDに分類しません。

RESCUEの単価はTikTokの `diamondCount`、YouTubeの `jewels` から取得します。
`price` は合計値なので、代用時は累積個数で割ります。連打の増分に単価を掛け、
例の「2ジュエル×5個＝10pt」を二重計算しません。価格不明の有料イベントは
未処理キューに保持してエラーを記録し、勝手なポイント数で消化しません。
スーパーチャット・普通のコメント・無料ギフトは効果を発動しません。
旧テスト割り当て（Tiny Diny Mic、バラ、一礼、有料ハート等）は廃止しました。

YouTubeの `giftId` はユーザー名・イベントIDまで含むため、そのまま設定キーにしません。
`hasGift` と `giftType=jewel` を確認したうえで、ギフト画像ファイル名に正規化します。
TikTokは `data.gift.giftId` を使います。名前は `displayName`、なければ `name` です。

## 無課金タップと同接

- TikTok: `connected.data.services` と `meta` の `totalLikeCount` を累計値のまま
  既存APIへ渡します。増分・リセット・試練開始時の基準・ハート無効期間は
  ゲーム側の既存ルールで処理します。再接続時は基準を取り直し、切断中のタップを
  まとめて後の試練に投入しません。
- YouTube: `reactions` の `data.reactions[].value` を全種類合算する既存APIに渡します。
  有料ハート画像やチャット本文の絵文字、動画の高評価数 `upVote` は無料リアクション
  として数えません。今回の受信例にはリアクションそのものがないため、公式の型と
  同じ形式のテストイベントで検証しています。
- 有効な配信枠の `viewer` をTikTok/YouTube別に合算し、次曲の同接ランクへ渡します。
  プレイ開始後のランク固定ルールはそのままです。

## 再送・再接続

初回の `connected` のコメント履歴、および `comments.data.options.init=true` は
基準として保存し、過去のギフトを発動しません。`comment` と `comments` の両方に対応。
再接続の履歴からは、初回接続時刻以降の未処理ギフトのみ回収します。

同じコメントのID・配信IDと個数を保存し、連打更新 `1→3→3` は `1+2` 個だけ扱います。
ラッキーギフトなどで別IDが返る場合は別イベントとして扱うため、配信前に実際の
わんコメの更新形式でも確認してください。ギフトは既存APIの一意な `event_id` と
永続キューを使い、API再起動でも重複発動を防ぎます。無料タップの送信待ちは
1.5秒で破棄し、後の曲へ貯め込みません。

状態: `Save/GiftAPI/onecomme-status.json`（接続状態・未送信数・最後のエラー）

ログ: `Stream/onecomme.log` / `Stream/onecomme-error.log`

受信履歴: `Save/GiftAPI/onecomme-state.json`（重複防止・未送信ギフト。配信中は削除しない）

個人の取得データ・コメント本文・プロフィール画像をGitHubへ保存しません。
自動テストは匿名の合成イベントで、WebSocketの分割フレーム/PING、HTTP転送、
履歴抑制・再送・連打差分・反応の種類・無料イベントの失効を確認します。

型の確認元: [OneComme ReactionAction](https://onecomme.com/sdk/interfaces/types_SDK.ReactionAction.html)、
[Reaction](https://onecomme.com/sdk/interfaces/types_Comment.Reaction.html)、
[ServiceMeta](https://onecomme.com/sdk/interfaces/types_Service.ServiceMeta.html)。
接続パスは公式 `@onecomme.com/onesdk` 配布コードの `/sub?p=...` と一致させています。
Roseの仮IDの確認元: [Lumia Streamのギフト受信例](https://dev.lumiastream.com/docs/alerts/tiktok/alert-tiktok-gift)。
