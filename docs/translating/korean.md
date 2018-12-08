# Korean translation style guide

## Rules
### 1. Formal or Informal? Formal!
> Use `foraml` grammar

Follow formal grammar of Korean. (Reference page: `https://www.korean.go.kr/`)
If there is a word which is informal but allowed, then use formal form except formal word is rarely used.
### 2. Form of sentence end
> **1.** `다, 나, 까` with punctuation marks **2.** `Noun form` without puncuation marks

If there is punctuation marks for end(**.**, **!**, **?**, etc), then use `다, 나, 까` according to contxt. If there is no punctuatio marks, then end with noun form.
### 3. Singluar and Plural
> Use `singular form`

Plural expression is not advanced in Korean languate. Use singular expression of word for both singular and plural form.
### 4. Loanword / Foreign language
> **1.** Follow `loanword orthography` for loanword **2.** Follow `Korean translation style guide` for foreign language

When translate loanword, then follow loanword orthography. For foreign language, then refer below contents. If there is no description for target word or sentence, then research usages in other websites and follow that form.

(Reference page: `https://www.korean.go.kr/front/foreignSpell/foreignSpellList.do?mn_id=96`)
### 5. Punctuation marks
> Follow `original sentence` 

If there is punctuation marks(**:**, **" "**, etc), then follow original sentence's space.

(ex: `New stream notifications: = 새 스트림 알림:` | :no_entry_sign: `새 스트림 알림_:` )
### 6. Template for Terms
> original word - (translation <**bold**>) <br>
> usage <*Italic*> <br>
> examples of usage <`code`> <br>
> description

## Terms
- collapse - **접기**

  Collapse is translated literally into '붕괴'. But it means like fold in Zulip, so we choose '접기' which has similar meaning of fold.

- draft - **임시 보관**

  Draft is used like temporary save in Zulip. So we translate draft into '임시 보관' which is consist of '임시' which means temporary and   '보관' which means save.

- generic bot - **범용 봇**

  generic bot is the bot which is able to webhook both incoming/outgoing. generic is oftenly translated into '일반', but its meaning is   similar to normal. So we use '범용' which is little bit more strange than '일반', but whose meaning is be able to use anywhere.

- history - **기록**
  
  *(Google, Youtube)*
  
  `Google: browsing history = 검색 기록`<br>
  `Youtube: watch history = 시청 기록`
  
  History can be translated with '역사', but it means study of past which is improper in this context. In this context, history is used   similarly to record. There are a lot of Korean words that means record; '기록', '이력', '내역'. Many websites use '기록' to history       because it is intuitive, so we choose to use it.

- invalid - **유효하지 않은**

  Invalid can be translated into '유효하지 않은' and '잘못된'. '잘못된' means wrong. We think it can't represent various invalid             situations, so we choose '유효하지 않은' which is not oftenly used but can handle wide range.

- linkifier - **링크 변환기**

  Linkifier transform regular expression to user defined link. So we translate it '링크 변환기' which means '링크' is phonetic writing of   of link, '변환기' is something transforms target source into target destination.

- message - **메시지**
  
  *(Naver, Google)*
  
  `Naver: 메시지 보내기`<br>
  `Google: Check your messages on your computer = 컴퓨터에서 메시지 확인하기`

- mute - **뮤트**

  *(Twitter)*
  
  `Twitter: Mute = 뮤트`
  
  Mute operation hide the messages and off the notification. Hide is translated into '숨기기', and 'Turn off' is translated into '끄기'.
  These two words are not compatible. So we choose '뮤트' which is phonetic writing of 'mute'. It is reasonable to use because Twitter     also translate it into '뮤트'.
  
- organization - **조직**
  
  *(Google)*
  
  `Google: Creating and Managing Organizations = 조직 생성 및 관리`
  
  There are many terms for organization('조직', '기관', '단체'). We choose '조직' which is generally used for formal group.

- permission - **권한**

  Permission is used with organization, stream, etc. And it means control the right in target group, so we translate it to '권한'
  which is similar to right.
 
- recipient - **받는 사람**

   *(Naver, Google(Gmail))*
   
   `Naver: 받는 사람 (이메일 서비스)`<br>
   `Google: 받는 사람 (Gmail)`

## Phrases
- narrow to - **한정해서 보기**

  We translate 'narrow to' into '한정해서 보기'. '한정해서 보기' may be strange expression to Korean, but there is 'narrow by' in other     file which is exactly translated into '로 한정하기'. So we choose '한정해서 보기' to maintain consistency.

- in (Somewhere) - **내의**

  There are frequently used two translations; '에 있는', '내의'. We think '~ 내의' is more formal to use, so we choose it.

## Other
- user / member - **사용자** / **회원**

  These two words are very similar, but we think they have different usages. 'User' is used to all the joined people in zulip, and the     'member' is specialized to people in organization or stream. So we translate user into '사용자', and member into '회원' which has more   meaning with belonging.
