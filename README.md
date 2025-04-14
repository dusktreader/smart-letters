[![Build Status](https://github.com/dusktreader/smart-letters/actions/workflows/push.yaml/badge.svg)](https://github.com/dusktreader/smart-letters/actions/workflows/push.yaml)
[![PyPI Versions](https://img.shields.io/pypi/v/smart-letters?style=plastic&label=pypi-version)](https://img.shields.io/pypi/v/smart-letters?style=plastic&label=pypi-version)

> [!IMPORTANT]
> I'm looking for a job right now! If you know of any openings that match my skill-set,
> please let me know! You can read my resume over at my
> [cv](https://github.com/dusktreader/cv) project. Thanks!!

# Smart Letters

[//]: # (Add an asciicast)

`smart-letters` is a CLI application designed to help you write cover letters rapidly
for specific job postings. By harnessing the power of OpenAI and Python, we can generate
a styled cover letter in PDF format in seconds. The slowest part is waiting for the
request from OpenAI to return!


## Quickstart

### 1. Install `smart-letters`:

```bash
pip install smart-letters
```

### 2. Configure `smart-letters`:

To see all the configuration options, run:

```bash
smart-letters config --help
```

The simplest working config would look like this:

```bash
smart-letters config bind --openai-api-key=<your-api-key> --resume-path=<path-to-resume-text> --candidate-name=<your-name>
```

### 3. Run `smart-letters`:

To see all the generation options, run:

```bash
smart-letters generate --help
```

An example run command would look like this:

```bash
smart-letters generate --company=ACME --position="Senior Engineering Lead" https://github.com/dusktreader/smart-letters/blob/main/etc/fake-listing.md
```

Follow the prompts and get your ready-to-send cover letter!


## Philosophy

There's a lot of pain involved with job searching these days. There's the struggle to
find postings that match your experience, expertise, and preferences. Then, there's the
frustration of all the different web-apps that are used to gather applications. Of
course, there's the rejection which is often automated; that is, if you get any
rejection notice instead of just silence.

However, probably the most frustrating part is the composition of cover letters. In the
current marketplace for tech talent, you need to be blasting out lots and lots of
applications. I've read horror stories on Reddit of seasoned devs that have sent out
literal thousands of applications over a several month span as they searched for their
next opportunity. Obviously, this is a process that needs to be fine tuned to maximize
production and maintain quality. The cover letter is a wrench thrown directly into the
machinery of the application process.

I understand that hiring teams may feel that cover letters are a useful tool. It helps
to screen out endless spam from automation. It's a way to ensure that the candidate has
at least read the posting. Plus, it gives you a snapshot into the personality and
motivation of the person applying. Sometimes I worry that the main reason that cover
letters are requested is that it takes only ticking a single check-box in the submission
form to many of these application SaaS platforms. In any case, writing the cover letter
is the main hot-spot of the application process.

Obviously, AI is a powerful tool for producing a lot of text very quickly. But, cover
letters produced by AI...read like they were written by AI. If you really want to get
good results, you need to tailor the letter to the job posting, refine your prompt, feed
it with personal information, refine the output, and then edit it by hand afterward to
get a good result.

Even that is quite boring and time consuming. So, as most good Python engineers like to
do, I decided to automate the boring stuff!


## Configuration

The `smart-letters` program stores its configuration in a file so that it can use
the same settings for many runs without having a super-cluttered command line. You can
check out the location where the config file is saved in the `config.py` module.

#### Sub-commands

There are several sub-commands that you can use to interact with your configuration:


#### bind

This is the core command. We used it in the Quickstart. This sub-command binds the
provided configuration options to the `smart-letters` program by storing them in a
config file.


#### update

Sometimes you want to just change one or two configuration options instead of supplying
all of them again. For that, you would use the `update` subcommand:

```bash
smart-letters config update --filename-prefix=awesome-letter
```

In this case, we only updated the filename prefix setting and left all the others as
they are.


#### unset

If you need to just unset one of the config options, you can do that with the `unset`
subcommand. You don't need to provide any value, just pass the option:

```bash
smart-letters config unset --filename-prefix
```


#### show

If you want to see the current configuration for `smart-letters`, use the show command:

```bash
smart-letters config show
```

It will produce some nicely formatted output that would look like this:

```
╭──────────────────────────── Current Configuration ───────────────────────────────────╮
│                                                                                      │
│   openai_api_key  -> <omitted>                                                       │
│   resume_path     -> /home/coyote/git-repos/personal/cv/README.md                    │
│   candidate_name  -> Wile E. Coyote                                                  │
│   filename_prefix -> cover-letter                                                    │
│   heading_path    -> /home/coyote/text/heading.md                                    │
│   sig_path        -> /home/coyote/images/sig.png                                     │
│                                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────╯
```


#### clear

If you want to just completely clear out your config, use the `clear` subcommand:

```bash
smart-letters config clear
```


### Settings

There are some notable settings that weren't used in the Quickstart. Let's go over them
here!


#### --filename-prefix

This one is really simple. By default, `smart-letters` will use the generic
"cover-letter" prefix for your file names. If you want to change it to something else,
you can set that here.


#### --heading-path

I, personally, like to include a heading in my letters that includes my name and some
basic contact information. You might want to supply one as well. You should note that
the contents of the letter are formatted as Markdown before they are rendered to a PDF,
so if your heading is formatted as markdown, it will get rendered nicely. Here's an
example heading:

```markdown
# Wile E. Coyote

📍 [Tucson, AZ](https://maps.app.goo.gl/5siCgp4pUymGPU499) /
📧 [wile.e.coyote@gmail.com](wile.e.coyote@gmail.com) /
🛠 [wile.e.coyote@github](https://github.com/wile.e.coyote)

---
```


#### --sig-path

I also like to include a signature image in my generated cover letter. If you include
one with this option, it will be placed in between your closing and your name:


```
Best regards,

[SIG HERE]

Wile E. Coyote
```


#### --output-directory

This option lets you set a target directory where letters will be saved when they are generated.
If you don't supply it, the default will be the current directory where you call the `smart-letters`
app.


#### --dev-prompt-path

By default, `smart-letters` uses a built-in developer prompt when it's generating letters. If you
want to have more control of the prompt that is used, you can supply a path to your own prompt
file.


#### --user-prompt-template-path

By default, `smart-letters` uses a built-in user prompt that is a mako template. The template has
the following values rendered into it at generation time:

* resume_text: The raw text of your resume
* posting_text: The raw text of the job posting
* example_text: An optional example letter to use as reference

You can supply a path to your own template if you want to have more control of the user prompt.


#### --editor-command

This option allows you to tell `smart-letters` which app to use to edit the generated letters
before they are finalized. If you don't supply it, `smart-letters` will attempt to use the
default editor configured for your system.


## Generation

There are a few options that are available on the `generate` sub-command that can be
useful. Let's go over them quickly:


### --company

This is simply the name of the company for which the letter will be generated. It is
used in creating the salutation and setting the filename.

If it's omitted, the salutation will just be generic:

```
Dear Hiring Manager,
```

If you set it, however, the salutation will incorporate it:

```
To the Hiring Team at <company>:
```


### --position

This option is only used for inclusion in the filename. It's useful to be able to
distinguish between many letters that you've generated over time.


### --example-letter

This option can be used to give the `generate` command an example (text) letter to
use for a reference when it's generating your cover letter.


### --render

By default `smart-letters` will ask you if you want to render the final letter to PDF
when it's done building it. With this option, you can control the answer to this
question ahead of time.


### --fake

When you are debugging `smart-letters`, the most time-consuming part is waiting for
OpenAI to generate the letter. If you want to skip that part, you can just pass this
option, and it will use a pre-baked letter body instead of calling out to OpenAI.


The `smart-letters` program stores its configuration in a file so that it can use
the same settings for many runs without having a super-cluttered command line. You can
check out the location where the config file is saved in the `config.py` module.


## Rendering

If you already have a Markdown letter that you would like to render to PDF, you can
use the `render` command. It will produce the letter by converting the Markdown to
HTML, styling it with CSS, and then rendering the result to a PDF.

There is options available on the `render` sub-command:


### --file-stem

By default, `render` will use the same file stem as the provided Markdown file. However,
if you want to change the stem, you can use this option.

For example, if the provided markdown file is named `my-letter.md`, the rendered PDF will
be named `my-letter.pdf`.
