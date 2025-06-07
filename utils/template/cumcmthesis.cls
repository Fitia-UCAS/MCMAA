\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{cumcmthesis}[2025/05/31 My own LaTeX Template for CUMCM]

%%%%% 条件开关定义
% 定义条件开关，用于控制打印颜色和前言页面
\newif\if@mcm@bwprint
\@mcm@bwprintfalse
\newif\if@mcm@preface
\@mcm@prefacetrue

%%%%% 承诺书相关命令
% 定义承诺书所需的变量命令
\newcommand*\mcm@tokens@keywords{}
\newcommand*\mcm@tokens@tihao{}
\newcommand*\mcm@tokens@baominghao{}
\newcommand*\mcm@tokens@schoolname{}
\newcommand*\mcm@tokens@membera{}
\newcommand*\mcm@tokens@memberb{}
\newcommand*\mcm@tokens@memberc{}
\newcommand*\mcm@tokens@supervisor{}
\newcommand*\mcm@tokens@yearinput{}
\newcommand*\mcm@tokens@monthinput{}
\newcommand*\mcm@tokens@dayinput{}

%%%%% 选项声明与处理
% 声明类选项，控制打印模式和前言
\DeclareOption{colorprint}{\@mcm@bwprintfalse}
\DeclareOption{bwprint}{\@mcm@bwprinttrue}
\DeclareOption{withoutpreface}{\@mcm@prefacefalse}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}

% 执行默认选项并处理传入选项
\ExecuteOptions{colorprint}
\ProcessOptions\relax

%%%%% 加载基础类和引擎检查
% 加载 article 类并要求使用 XeLaTeX 引擎
\LoadClass[a4paper,12pt]{article}
\RequirePackage{ifxetex}
\RequireXeTeX
\ifxetex\else
  \ClassError{cumcmthesis}{You must use the `xelatex' driver\MessageBreak Please choose `xelatex'}{%
    Just choose `xelatex', no `pdflatex' or `latex' and so on.}
\fi

%%%%% 加载宏包：中文支持与字体
% 支持中文和字体设置
\RequirePackage{ctex}
\RequirePackage{fontspec}

%%%%% 加载宏包：页面与排版
% 设置页面布局和排版相关宏包
\RequirePackage{geometry}
\RequirePackage{setspace} % 首行缩进与行距
\RequirePackage{caption} % 浮动体标题设置
\RequirePackage{enumitem} % 定制列表环境
\RequirePackage{ulem} % 下划线支持
\RequirePackage{calc} % 尺寸计算
\RequirePackage[framemethod=TikZ]{mdframed} % 带框环境
\RequirePackage[titletoc,title]{appendix} % 附录支持

%%%%% 加载宏包：数学与单位
% 数学公式和单位格式化
\RequirePackage{amsmath}
\RequirePackage{amsfonts}
\RequirePackage{amssymb}
\RequirePackage{bm}
\RequirePackage{siunitx}
\sisetup{per-mode=symbol} % 设置单位格式，例如 kW/m^2

%%%%% 加载宏包：颜色与图形
% 颜色、图片和绘图支持
\RequirePackage{xcolor}
\RequirePackage{graphicx}
\RequirePackage{float}
\RequirePackage{adjustbox} % 灵活的图片调整
\RequirePackage{tikz} % 绘图支持
\RequirePackage{pifont} % \ding 符号支持

%%%%% 加载宏包：表格
% 表格相关宏包
\RequirePackage{array}
\RequirePackage{longtable}
\RequirePackage{colortbl}
\RequirePackage{booktabs}
\RequirePackage{tabularx}
\RequirePackage{multirow}
\RequirePackage{bigstrut}
\RequirePackage{bigdelim}

%%%%% 加载宏包：代码与算法
% 代码展示与算法环境
\RequirePackage[most]{tcolorbox}
\tcbuselibrary{breakable} % 支持代码换页
\RequirePackage{listings} % 保留 listings 兼容性
% \RequirePackage[linesnumbered,ruled]{algorithm2e}
\RequirePackage{cprotect} % 保护脆弱命令

%  这三个组合加上浮动体支持跨页算法
\RequirePackage{algorithm}        % 算法浮动体环境
\RequirePackage{algpseudocode}    % 伪代码语法支持
\RequirePackage{float}            % 浮动体精确控制 (H 位置限定符)
\RequirePackage{lipsum}          % 占位文本生成 (调试用，正式文档可移除)

%%%%% 算法环境定义
% 定义算法计数器和 algorithmsteps 环境
\newcounter{algcounter} % 独立算法计数器
\newenvironment{algorithmsteps}[1]{%
  \stepcounter{algcounter}
  \setcounter{stepcounter}{0}
  \begin{longtable}{p{0.98\textwidth}}
    \toprule
    \textbf{\, Algorithm \thealgcounter: #1} \\
    \midrule
    \endfirsthead
    \toprule
    \textbf{\, Algorithm \thealgcounter: #1} \\
    \midrule
    \endhead
    \bottomrule
    \hfill \textit{续下页} \\
    \endfoot
    \bottomrule
    \endlastfoot
}{%
  \end{longtable}
  \addtocounter{table}{-1}
}
% 长算法环境
\newenvironment{breakablealgorithm}{%
  \begin{center}
    \refstepcounter{algorithm}%
    \hrule height.8pt depth0pt \kern2pt%
    \renewcommand{\caption}[2][\relax]{%
      {\raggedright\textbf{\ALG@name~\thealgorithm} ##2\par}%
      \ifx\relax##1\relax
        \addcontentsline{loa}{algorithm}{\protect\numberline{\thealgorithm}##2}%
      \else
        \addcontentsline{loa}{algorithm}{\protect\numberline{\thealgorithm}##1}%
      \fi
      \kern2pt\hrule\kern2pt
    }%
    % 临时恢复原始 tabular 环境
    \let\tabular\mcm@oldtabular
    \let\endtabular\mcm@endoldtabular
  }{%
    \kern2pt\hrule\relax%
  \end{center}
}

% 定义 \addstep 命令
\newcounter{stepcounter}
\newcommand{\addstep}[2][]{%
  \stepcounter{stepcounter}
  \begin{minipage}[t]{0.98\textwidth}
    \noindent \textbf{Step \thestepcounter : #1}
    \par
    {\setlength{\leftskip}{2em}
    #2
    \par}
  \end{minipage}
  \vspace{0.01em} \\
}

%%%%% 标题与符号定义
% 定义带圈数字
\newcommand{\circled}[1]{%
  \ifcase#1%
    \or {\fontspec{SimHei} ①}\or {\fontspec{SimHei} ②}\or {\fontspec{SimHei} ③}\or {\fontspec{SimHei} ④}\or {\fontspec{SimHei} ⑤}\or {\fontspec{SimHei} ⑥}\or {\fontspec{SimHei} ⑦}\or {\fontspec{SimHei} ⑧}\or {\fontspec{SimHei} ⑨}\or {\fontspec{SimHei} ⑩}%
    \or {\fontspec{SimHei} ⑪}\or {\fontspec{SimHei} ⑫}\or {\fontspec{SimHei} ⑬}\or {\fontspec{SimHei} ⑭}\or {\fontspec{SimHei} ⑮}\or {\fontspec{SimHei} ⑯}\or {\fontspec{SimHei} ⑰}\or {\fontspec{SimHei} ⑱}\or {\fontspec{SimHei} ⑲}\or {\fontspec{SimHei} ⑳}%
  \else%
    \tikz[baseline=(char.base)]{\node[customcircle] (char) {#1};}%
  \fi%
}

% 重定义 \ding 命令
\let\oldding\ding
\renewcommand{\ding}[1][108]{%
  \oldding{#1}\hspace{0em}
}

% 定义方框符号
\newcommand{\rectedsymbol}{■}

% 定义标题计数器
\newcounter{numtitle}[subsubsection]
\newcounter{circtitle}[numtitle]
\newcounter{dingtitle}[circtitle]
\newcounter{squatitle}[dingtitle]

% 定义自动编号标题命令
\newcommand{\numtitle}[2][\par]{%
  \stepcounter{numtitle}%
  \noindent\textbf{(\hspace{0.1em}\arabic{numtitle}\hspace{0.1em})#2}%
  #1%
}

\newcommand{\circtitle}[2][\par]{%
  \stepcounter{circtitle}%
  \noindent\hspace{-0.25em}\circled{\value{circtitle}}\textbf{#2}%
  #1%
}

\newcommand{\dingtitle}[2][\par]{%
  \stepcounter{dingtitle}%
  \noindent\hspace{2.0em}\ding\textbf{\arabic{dingtitle}.\thinspace#2}%
  #1%
}

\newcommand{\squatitle}[2][\par]{%
  \stepcounter{squatitle}%
  \noindent\hspace{2.0em}\textbf{\rectedsymbol \thinspace \roman{squatitle}\thinspace. #2}%
  #1%
}

% 定义无编号标题
\newcommand{\plaintitle}[1]{%
  \noindent\textbf{#1：}%
  \par%
}

%%%%% 目录与子图
% 目录和子图设置
\RequirePackage{subcaption}
\RequirePackage[titles]{tocloft}
\renewcommand{\cftsecdotsep}{4.5}
\setlength{\cftbeforesecskip}{7pt}
\setlength{\cftbeforesubsecskip}{3pt}
\renewcommand{\cftsecfont}{\bfseries\zihao{-4}\heiti}
\renewcommand{\cftsecleader}{\cftdotfill{\cftsecdotsep}}
\renewcommand{\cftsecaftersnumb}{\hskip.4em}

%%%%% 代码环境定义
% 定义代码颜色
\definecolor{dkgreen}{rgb}{0,0.6,0}
\definecolor{gray}{rgb}{0.50,0.50,0.50}
\definecolor{mauve}{rgb}{0.508,0,0.82}

% 定义代码文件输入环境
\newtcbinputlisting[auto counter]{\codefile}[2][]{%
  listing file={#2},
  title={\lstlistingname~\thetcbcounter: #1},
  colback=gray!5,
  colframe=gray!35,
  fonttitle=\bfseries,
  listing only,
  left=2em,
  boxrule=1pt,
  listing options={
    basicstyle=\small\ttfamily,
    language=#1,
    breaklines=true,
    breakatwhitespace=true,
    tabsize=3,
    numbers=left,
    numberstyle=\tiny\color{gray},
    keywordstyle=\color{blue},
    commentstyle=\color{dkgreen},
    stringstyle=\color{mauve},
    showtabs=false,
  },
  enhanced,
  breakable,
}

% 定义代码块环境
\newtcblisting[auto counter]{codeblock}[1][]{%
  title={\lstlistingname~\thetcbcounter: #1},
  colback=gray!5,
  colframe=gray!35,
  fonttitle=\bfseries,
  listing only,
  left=2em,
  boxrule=1pt,
  listing options={
    basicstyle=\small\ttfamily,
    language=#1,
    breaklines=true,
    breakatwhitespace=true,
    tabsize=3,
    numbers=left,
    numberstyle=\tiny\color{gray},
    keywordstyle=\color{blue},
    commentstyle=\color{dkgreen},
    stringstyle=\color{mauve},
    showtabs=false,
  },
  enhanced,
  breakable,
}

%%%%% 环境字体设置
% 为数学环境设置正常字体
\RequirePackage{etoolbox}
\AtBeginEnvironment{definition}{\normalfont}
\AtBeginEnvironment{theorem}{\normalfont}
\AtBeginEnvironment{lemma}{\normalfont}
\AtBeginEnvironment{corollary}{\normalfont}
\AtBeginEnvironment{assumption}{\normalfont}
\AtBeginEnvironment{conjecture}{\normalfont}
\AtBeginEnvironment{axiom}{\normalfont}
\AtBeginEnvironment{principle}{\normalfont}
\AtBeginEnvironment{problem}{\normalfont}
\AtBeginEnvironment{example}{\normalfont}
\AtBeginEnvironment{proof}{\normalfont}
\AtBeginEnvironment{solution}{\normalfont}

%%%%% 超链接设置
% 配置 hyperref 宏包
\RequirePackage{hyperref}
\hypersetup{%
  pdfencoding=auto,
  psdextra,
  pdfstartview=FitH,
  CJKbookmarks=true,
  bookmarksnumbered=true,
  bookmarksopen=true,
  allcolors=black,
  breaklinks=true
}

%%%%% 书签命令简化
% 禁用书签中可能导致错误的命令，确保 PDF 书签格式正确
\pdfstringdefDisableCommands{%
  \def\cftdotfill{} % 禁用目录填充点
  \def\leavevmode@ifvmode{} % 禁用模式切换命令
  \def\kern{} % 禁用间距调整
  \def\hskip{} % 禁用水平间距
  \def\thinspace{} % 禁用窄间距
  \def\.{} % 禁用可能出现的点号命令
}

%%%%% 交叉引用设置
% 加载 cleveref 宏包以支持智能自动化交叉引用
\RequirePackage{cleveref}

%%%%% 页面布局设置
% 配置页面边距和行距
\geometry{top=25mm, bottom=25mm, left=25mm, right=25mm}
\renewcommand*{\baselinestretch}{1.38}

% 修改 tabular 环境，使表格行间距与正文一致
\let\mcm@oldtabular\tabular
\let\mcm@endoldtabular\endtabular
\renewenvironment{tabular}{%
  \bgroup%
  \renewcommand{\arraystretch}{1.38}%
  \mcm@oldtabular%
}{%
  \mcm@endoldtabular\egroup%
}

% 设置每段首行缩进两个汉字
\setlength\parindent{2em}

%%%%% 字体设置
% 配置英文字体和中文字体
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setCJKfamilyfont{kai}[BoldFont={SimHei}, AutoFakeBold=2.5]{KaiTi}
\setCJKfamilyfont{hei}[BoldFont=*, AutoFakeBold=2.5]{SimHei}
\setCJKfamilyfont{song}[BoldFont={SimHei}, AutoFakeBold=2.5]{SimSun}

% 定义字体切换命令
\newcommand*{\kai}{\CJKfamily{kai}}
\newcommand*{\song}{\CJKfamily{song}}
\newcommand*{\hei}{\CJKfamily{hei}}

% 设置正文字体大小和公式间距
\renewcommand\normalsize{%
  \@setfontsize\normalsize{12.05}{14.45}%
  \abovedisplayskip 6\p@ \@plus2\p@
  \abovedisplayshortskip 0\z@ \@plus3\p@
  \belowdisplayshortskip 0\p@ \@plus3\p@
  \belowdisplayskip 4\p@ \@plus2\p@
}

%%%%% 数学与定理环境
% 定义数学环境和定理类环境
\newtheorem{definition}{\mcm@cap@definition}
\newtheorem{theorem}{\mcm@cap@theorem}
\newtheorem{lemma}{\mcm@cap@lemma}
\newtheorem{corollary}{\mcm@cap@corollary}
\newtheorem{assumption}{\mcm@cap@assumption}
\newtheorem{conjecture}{\mcm@cap@conjecture}
\newtheorem{axiom}{\mcm@cap@axiom}
\newtheorem{principle}{\mcm@cap@principle}
\newtheorem{problem}{\mcm@cap@problem}
\newtheorem{example}{\mcm@cap@example}
\newtheorem{proof}{\mcm@cap@proof}
\newtheorem{solution}{\mcm@cap@solution}

%%%%% 浮动环境设置
% 调整浮动环境比例，优化页面布局
\renewcommand*{\textfraction}{0.05} % 降低文字占比要求
\renewcommand*{\topfraction}{0.9} % 顶部浮动环境最大比例
\renewcommand*{\bottomfraction}{0.8} % 底部浮动环境最大比例
\renewcommand*{\floatpagefraction}{0.85} % 单独浮动页最小占比

%%%%% 图片设置
% 设置图片支持的扩展名和搜索路径
\DeclareGraphicsExtensions{.pdf, .eps, .jpg, .png}
\graphicspath{{figures/}{figure/}{pictures/}{picture/}{pic/}{pics/}{image/}{images/}}

% 配置图表标题格式
\DeclareCaptionFont{song}{\songti}
\DeclareCaptionFont{minusfour}{\zihao{-4}}
\captionsetup[figure]{%
  format=hang, % 标题第二行起缩进
  labelsep=quad, % 标签与标题间距
  font={song, minusfour}, % 宋体小四
  position=bottom % 标题位置由 \caption 决定
}
\captionsetup[table]{%
  format=hang, % 标题第二行起缩进
  labelsep=quad, % 标签与标题间距
  font={song, minusfour}, % 宋体小四
  position=top % 标题位置由 \caption 决定
}

%%%%% 列表环境设置
% 定制列表环境的间距和缩进
\setlist{%
  topsep=0.3em, % 列表顶部垂直间距
  partopsep=0pt, % 列表前空行时的额外间距
  itemsep=0ex plus 0.1ex, % 列表项间垂直间距
  parsep=0pt, % 列表项内段落间距
  leftmargin=1.5em, % 左边界到列表的距离
  rightmargin=0em, % 右边界到列表的距离
  labelsep=0.50em, % 标签与文本间距
  labelwidth=2em % 标签宽度
}

%%%%% 交叉引用格式设置
% 配置 cleveref 的交叉引用格式
\crefformat{figure}{#2图~#1#3}
\crefrangeformat{figure}{图~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{figure}{图~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{table}{#2表~#1#3}
\crefrangeformat{table}{表~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{table}{表~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{equation}{#2~(#1#3)}
\crefrangeformat{equation}{~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{equation}{~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{definition}{#2\mcm@cap@definition~#1#3}
\crefrangeformat{definition}{\mcm@cap@definition~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{definition}{\mcm@cap@definition~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{theorem}{#2\mcm@cap@theorem~#1#3}
\crefrangeformat{theorem}{\mcm@cap@theorem~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{theorem}{\mcm@cap@theorem~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{lemma}{#2\mcm@cap@lemma~#1#3}
\crefrangeformat{lemma}{\mcm@cap@lemma~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{lemma}{\mcm@cap@lemma~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{corollary}{#2\mcm@cap@corollary~#1#3}
\crefrangeformat{corollary}{\mcm@cap@corollary~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{corollary}{\mcm@cap@corollary~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{assumption}{#2\mcm@cap@assumption~#1#3}
\crefrangeformat{assumption}{\mcm@cap@assumption~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{assumption}{\mcm@cap@assumption~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{conjecture}{#2\mcm@cap@conjecture~#1#3}
\crefrangeformat{conjecture}{\mcm@cap@conjecture~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{conjecture}{\mcm@cap@conjecture~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{axiom}{#2\mcm@cap@axiom~#1#3}
\crefrangeformat{axiom}{\mcm@cap@axiom~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{axiom}{\mcm@cap@axiom~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{principle}{#2\mcm@cap@principle~#1#3}
\crefrangeformat{principle}{\mcm@cap@principle~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{principle}{\mcm@cap@principle~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{problem}{#2\mcm@cap@problem~#1#3}
\crefrangeformat{problem}{\mcm@cap@problem~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{problem}{\mcm@cap@problem~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{example}{#2\mcm@cap@example~#1#3}
\crefrangeformat{example}{\mcm@cap@example~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{example}{\mcm@cap@example~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{proof}{#2\mcm@cap@proof~#1#3}
\crefrangeformat{proof}{\mcm@cap@proof~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{proof}{\mcm@cap@proof~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

\crefformat{solution}{#2\mcm@cap@solution~#1#3}
\crefrangeformat{solution}{\mcm@cap@solution~(#3#1#4)\;\~{}\;(#5#2#6)}
\crefmultiformat{solution}{\mcm@cap@solution~(#2#1#3)}{和~(#2#1#3)}{，(#2#1#3)}{和~(#2#1#3)}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%% 文档封面与标题页
% 重定义 \maketitle 命令以生成封面和承诺书页面
\renewcommand{\maketitle}{\par
	\begingroup
      \newpage
      \global\@topnum\z@   % Prevents figures from going at top of page.
      \@maketitle
    \endgroup
  \global\let\thanks\relax
  \global\let\maketitle\relax
  \global\let\@maketitle\relax
  \global\let\@thanks\@empty
  \global\let\@author\@empty
  \global\let\@date\@empty
  \global\let\@title\@empty
  \global\let\title\relax
  \global\let\author\relax
  \global\let\date\relax
  \global\let\and\relax
}

% 定义封面和承诺书的具体内容
\def\@maketitle{%
  \newpage
  \if@mcm@preface
  \null
  % 承诺书页面
  \vskip2ex
  \thispagestyle{empty}
  {\zihao{4}\noindent\mcm@commit@string@headname\\[-8pt]
  \noindent\rule[5pt]{\textwidth-1.34em}{.5pt}\par}
  \begin{center}%
    {\zihao{-3}\bfseries\heiti \mcm@commit@string@titlea \par}%
    {\vskip1ex\zihao{3}\bfseries\songti \mcm@commit@string@titleb \par}
  \end{center}
    {\zihao{-4} \mcm@commit@string@contents \par}
    {\vskip1ex\zihao{-4}
    \renewcommand{\ULthickness}{0.4pt}\setlength{\ULdepth}{2pt}
	\begin{spacing}{1.6}
    \mcm@commit@string@problemnum\uline{\mbox{\kern1em}\mcm@tokens@tihao\hfill}\makebox[0.66em]{}\par
    \mcm@commit@string@signupnum\uline{\mbox{\kern1em}\mcm@tokens@baominghao\hfill}\makebox[0.66em]{}\par
    \mcm@commit@string@schoolname\uline{\hfill\mcm@tokens@schoolname\hfill}\makebox[0.66em]{}\par
	\end{spacing}
    \newlength{\mcm@lenB}
    \settowidth{\mcm@lenB}{\mcm@commit@string@membername\mbox{\hspace{1em}}1.}
    \setlength{\mcm@lenB}{\textwidth-\mcm@lenB}
    % 不这样做右边难以对齐!
	\vskip2em%
    \hspace*{2em}\mcm@commit@string@membername
    \begin{minipage}[t]{\mcm@lenB}
   	1.\uline{\mbox{\kern1em}\mcm@tokens@membera\hfill} \makebox[0.46em]{}\par\vspace*{.37cm}
   	2.\uline{\mbox{\kern1em}\mcm@tokens@memberb\hfill} \makebox[0.46em]{}\par\vspace*{.37cm}
   	3.\uline{\mbox{\kern1em}\mcm@tokens@memberc\hfill} \makebox[0.46em]{}\par
   \end{minipage}\par\vskip2em
    \mcm@commit@string@supervisorname\uline{\mbox{\hspace{1em}}\mcm@tokens@supervisor\hfill}\makebox[0.66em]{}\par
    \hspace{0.1cm} （{\kaishu 指导教师签名意味着对参赛队的行为和论文的真实性负责}）
    %{\kaishu\mcm@commit@string@inform\par}
    \vskip2ex
    \newlength{\mcm@lenA}
    \settowidth{\mcm@lenA}{请仔细核对，提交后将不再允许做任何修改。如}% 虽然"日期"刚好在"错误"下面, 但注意"日期"还会缩进, 所以要省去"填写""两字
    \hspace*{\mcm@lenA}\mcm@commit@string@date\hspace{0.50em}\uline{\hfill\mbox{\kern1em}\mcm@tokens@yearinput\mbox{\kern1em}\hfill}%
    \mcm@commit@string@year\uline{\hfill\mcm@tokens@monthinput\hfill}\mcm@commit@string@month%
    \uline{\hfill\mcm@tokens@dayinput\hfill}\mcm@commit@string@day\makebox[1em]{}\par}
    \vskip1ex
    {\kaishu\bfseries\mcm@commit@string@inform\par}
	\vfill
	\null
  % 编号专用页
	\else
	\fi
	\makeothertitle
}

%%%%% 编号专用页定义
% 定义编号专用页，用于赛区和全国评阅
\def\makeothertitle{%
  \if@mcm@preface
  \par
  \newpage
  \null
  \thispagestyle{empty}
  {\zihao{4}\noindent\begin{tabularx}{\textwidth}{cXcX@{}}
  \mcm@numberpage@string@headname & & \mcm@numberpage@string@allcountrynum&\\[-5pt]
  \mcm@numberpage@string@headnameb & &\mcm@numberpage@string@allcountrynumb&\\
  \cline{2-2}\cline{4-4}
  \end{tabularx}
  \vspace*{1.2em}
  \noindent\rule{\textwidth}{1pt}\par}
  \begin{center}
  {\zihao{4}\bfseries\heiti \mcm@numberpage@string@titlea\par}
  {\vskip1ex\zihao{3}\songti \bfseries\mcm@numberpage@string@titleb\par}
  \end{center}\par
  {%
  \zihao{4}
  \vskip3em
  \hspace*{2em}\mcm@numberpage@string@appraiselog
  \par
  \newlength{\mcm@lenC}
  \setlength{\mcm@lenC}{\textwidth-8.72em}
  \setlength{\mcm@lenC}{\mcm@lenC/6}
  \newlength{\mcm@lenD}
  \settoheight{\mcm@lenD}{\mcm@numberpage@string@reviewer}
  \setlength{\mcm@lenD}{\mcm@lenD+2em}
  \newlength{\mcm@lenF}
  \settoheight{\mcm@lenF}{\mcm@numberpage@string@remarks}
  \setlength{\mcm@lenF}{\mcm@lenF+2em}
  \newcolumntype{P}{@{}p{\mcm@lenC}@{}}
  \hspace*{1.5em}\begin{tabular}{|!{\hspace{4pt}}c!{\hspace{4pt}}|*{6}{P|}}
   \hline
   \rule{0pt}{\mcm@lenD}\raisebox{0.6em}[0pt][0pt]{\mcm@numberpage@string@reviewer} & & & & & &  \\\cline{1-7}
   \rule{0pt}{\mcm@lenF}\raisebox{0.6em}[0pt][0pt]{\mcm@numberpage@string@remarks} & & & & & &  \\
   \hline
  \end{tabular}\par
  \vskip5em
  \hspace*{2em}\mcm@numberpage@string@countrynum}
  \vfill
  {\zihao{-4}\kaishu\bfseries\mcm@numberpage@string@inform\par}
  \null
  \newpage
  \null
  \setcounter{page}{1}
  {\centering \zihao{3}\bfseries \@title\par}
  \vskip1ex
  \else
  \setcounter{page}{1}
  {\centering \zihao{3}\bfseries \@title\par}
  \vskip1ex
  \fi
}

%%%%% 中文标题名称设置
% 设置标准中文标题名称
\renewcommand\contentsname{\mcm@cap@contentsname}
\renewcommand\listfigurename{\mcm@cap@listfigurename}
\renewcommand\listtablename{\mcm@cap@listtablename}
\renewcommand\refname{\mcm@cap@refname}
\renewcommand\indexname{\mcm@cap@indexname}
\renewcommand\figurename{\mcm@cap@figurename}
\renewcommand\tablename{\mcm@cap@tablename}
\renewcommand\appendixname{\mcm@cap@appendixname}
\renewcommand\abstractname{\mcm@cap@abstractname}

%%%%% 标题与目录格式设置
% 设置目录深度和节标题格式
\setcounter{secnumdepth}{3}
\def\@seccntformat#1{\csname the#1\endcsname\ }
\renewcommand\thesection{\chinese{section}、}
\renewcommand\thesubsection{\arabic{section}\thinspace.\thinspace\arabic{subsection}}
\renewcommand\thesubsubsection{\thesubsection\thinspace.\thinspace\arabic{subsubsection}}
\renewcommand\section{\@startsection{section}{1}{\z@}%
 	{-3.5ex \@plus -1ex \@minus -.2ex}%
	{2.3ex \@plus.2ex}%
	{\centering\normalfont\Large\bfseries}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
	{-3.25ex\@plus -1ex \@minus -.2ex}%
	{1.5ex \@plus .2ex}%
	{\normalfont\large\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
	{-3.25ex\@plus -1ex \@minus -.2ex}%
	{1.5ex \@plus .2ex}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\paragraph{\@startsection{paragraph}{4}{\z@}%
	{3.25ex \@plus1ex \@minus.2ex}%
	{-1em}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\subparagraph{\@startsection{subparagraph}{5}{\parindent}%
	 {3.25ex \@plus1ex \@minus .2ex}%
	 {-1em}%
	 {\normalfont\normalsize\bfseries}}

%%%%% 摘要与关键词环境
% 重定义摘要环境
\renewenvironment{abstract}{%
  \if@twocolumn
		\section*{\abstractname}%
	\else
	 \begin{center}%
	{\zihao{4}\bfseries \abstractname\vspace{-.5em}\vspace{\z@}}%
	 \end{center}%
 	 \quotation
	\fi}
	{\if@twocolumn\else\endquotation\newpage\null\fi}

% 重定义 quotation 环境
\renewenvironment{quotation}
	{\list{}{\listparindent 2em%
	 \itemindent \listparindent
	 \rightmargin\z@
	 \leftmargin\z@
	 \parsep \z@ \@plus\p@}%
	\item\relax}
	{\endlist}

% 定义关键词命令
\newcommand\keywords[1]{%
	\renewcommand{\mcm@tokens@keywords}{#1}
	\par
	\vskip1ex
	{\noindent\zihao{-4}\heiti\mcm@cap@keywordsname：}~{\mcm@tokens@keywords}
}

%%%%% 参考文献环境
% 重定义参考文献环境
\renewenvironment{thebibliography}[1]
     {\section*{\refname}%
      \@mkboth{\MakeUppercase\refname}{\MakeUppercase\refname}%
      \list{\@biblabel{\@arabic\c@enumiv}}%
           {\settowidth\labelwidth{\@biblabel{#1}}%
            \leftmargin\labelwidth
            \advance\leftmargin\labelsep
            \@openbib@code
            \usecounter{enumiv}%
            \let\p@enumiv\@empty
            \renewcommand\theenumiv{\@arabic\c@enumiv}}%
      \sloppy
      \clubpenalty4000
      \@clubpenalty \clubpenalty
      \widowpenalty4000%
      \sfcode`\.\@m}
     {\def\@noitemerr
       {\@latex@warning{Empty `thebibliography' environment}}%
      \endlist}

%%%%% 承诺书变量命令
% 定义承诺书相关变量命令
\newcommand*\tihao[1]{%
	\renewcommand{\mcm@tokens@tihao}{#1}}
\newcommand*\baominghao[1]{%
	\renewcommand{\mcm@tokens@baominghao}{#1}}
\newcommand*\schoolname[1]{%
	\renewcommand{\mcm@tokens@schoolname}{#1}}
\newcommand*\membera[1]{%
	\renewcommand{\mcm@tokens@membera}{#1}}
\newcommand*\memberb[1]{%
	\renewcommand{\mcm@tokens@memberb}{#1}}
\newcommand*\memberc[1]{%
	\renewcommand{\mcm@tokens@memberc}{#1}}
\newcommand*\supervisor[1]{%
	\renewcommand{\mcm@tokens@supervisor}{#1}}
\newcommand*\yearinput[1]{%
	\renewcommand{\mcm@tokens@yearinput}{#1}}
\newcommand*\monthinput[1]{%
	\renewcommand{\mcm@tokens@monthinput}{#1}}
\newcommand*\dayinput[1]{%
	\renewcommand{\mcm@tokens@dayinput}{#1}}

%%%%% 初始化常量
% 数学定理相关常量
\newcommand*{\mcm@cap@definition}{定义}
\newcommand*{\mcm@cap@theorem}{定理}
\newcommand*{\mcm@cap@lemma}{引理}
\newcommand*{\mcm@cap@corollary}{推论}
\newcommand*{\mcm@cap@assumption}{假设}
\newcommand*{\mcm@cap@conjecture}{猜想}
\newcommand*{\mcm@cap@axiom}{公理}
\newcommand*{\mcm@cap@principle}{定律}
\newcommand*{\mcm@cap@problem}{问题}
\newcommand*{\mcm@cap@example}{例}
\newcommand*{\mcm@cap@proof}{证明}
\newcommand*{\mcm@cap@solution}{解}

% 中文标题名称常量
\newcommand*{\mcm@cap@contentsname}{目录}
\newcommand*{\mcm@cap@listfigurename}{插图清单}
\newcommand*{\mcm@cap@listtablename}{附表清单}
\newcommand*{\mcm@cap@refname}{参考文献}
\newcommand*{\mcm@cap@indexname}{索引}
\newcommand*{\mcm@cap@figurename}{图}
\newcommand*{\mcm@cap@tablename}{表}
\newcommand*{\mcm@cap@appendixname}{附录}
\newcommand*{\mcm@cap@abstractname}{摘要}
\newcommand*{\mcm@cap@keywordsname}{关键字}

% 承诺书相关常量
\newcommand*\mcm@commit@string@headname{赛区评阅编号（由赛区组委会填写）：}
\newcommand*\mcm@commit@string@titlea{\the\year 高教社杯全国大学生数学建模竞赛}
\newcommand*\mcm@commit@string@titleb{承\hspace{1em}诺\hspace{1em}书}
\newcommand\mcm@commit@string@contents{\quotation
我们仔细阅读了《全国大学生数学建模竞赛章程》和《全国大学生数学建模竞赛参赛规则》（以下简称 “竞赛章程和参赛规则”，可从http://www.mcm.edu.cn下载）。

我们完全清楚，在竞赛开始后参赛队员不能以任何方式，包括电话、电子邮件、“贴吧”、QQ群、微信群等，与队外的任何人（包括指导教师）交流、讨论与赛题有关的问题；无论主动参与讨论还是被动接收讨论信息都是严重违反竞赛纪律的行为。

%我们完全清楚，在竞赛中必须合法合规地使用文献资料和软件工具，不能有任何侵犯知识产权的行为。否则我们将失去评奖资格，并可能受到严肃处理。

{\bfseries\song 我们以中国大学生名誉和诚信郑重承诺，严格遵守竞赛章程和参赛规则，以保证竞赛的公正、公平性。如有违反竞赛章程和参赛规则的行为，我们将受到严肃处理。}

我们授权全国大学生数学建模竞赛组委会，可将我们的论文以任何形式进行公开展示（包括进行网上公示，在书籍、期刊和其他媒体进行正式或非正式发表等）。
\endquotation
}
\newcommand*\mcm@commit@string@problemnum{我们参赛选择的题号（从A/B/C/D/E中选择一项填写）：}
\newcommand*\mcm@commit@string@signupnum{我们的报名参赛队号（12位数字全国统一编号）：}
\newcommand*\mcm@commit@string@schoolname{参赛学校（完整的学校全称，不含院系名）：}
\newcommand*\mcm@commit@string@membername{参赛队员 (打印并签名) ：}
\newcommand*\mcm@commit@string@supervisorname{指导教师或指导教师组负责人  (打印并签名)：}
\newcommand\mcm@commit@string@inform{\quotation
\noindent{（\bfseries\kai 请勿改动此页内容和格式。此承诺书打印签名后作为纸质论文的封面，注意电子版论文中不得出现此页。%
以上内容请仔细核对，如填写错误，论文可能被取消评奖资格。）}
\endquotation
}
\newcommand*\mcm@commit@string@date{日期:}
\newcommand*\mcm@commit@string@year{年}
\newcommand*\mcm@commit@string@month{月}
\newcommand*\mcm@commit@string@day{日}
\newcommand*\mcm@commit@string@appraisenum{赛区评阅编号（由赛区组委会评阅前进行编号）：}

% 编号专用页相关常量
\newcommand*\mcm@numberpage@string@headname{赛区评阅编号：}
\newcommand*\mcm@numberpage@string@headnameb{（由赛区填写）}
\newcommand*\mcm@numberpage@string@allcountrynum{全国评阅编号：}
\newcommand*\mcm@numberpage@string@allcountrynumb{（全国组委会填写）}
\newcommand*\mcm@numberpage@string@titlea{\the\year 高教社杯全国大学生数学建模竞赛}
\newcommand*\mcm@numberpage@string@titleb{编\hspace{.5em}号\hspace{.5em}专\hspace{.5em}用\hspace{.5em}页}
\newcommand*\mcm@numberpage@string@appraiselog{赛区评阅记录（可供赛区评阅时使用）：}
\newcommand\mcm@numberpage@string@reviewer{\shortstack{评\\ 阅\\ 人}}
\newcommand\mcm@numberpage@string@remarks{\shortstack{备\\ 注}}
\newcommand*\mcm@numberpage@string@countrynum{送全国评阅统一编号:\par \hspace*{2em}（赛区组委会填写）}
\newcommand\mcm@numberpage@string@inform{\quotation
\noindent（{\bfseries\kai 请勿改动此页内容和格式。此编号专用页仅供赛区和全国评阅使用，参赛队打印后装订到纸质论文的第二页上。
注意电子版论文中不得出现此页。}）
\endquotation
}

%%%%% 文献引用命令
% 定义上标文献引用命令
\newcommand{\upcite}[1]{$^{\mbox{\scriptsize \cite{#1}}}$}
\newcommand{\supercite}[1]{\textsuperscript{\textsuperscript{\cite{#1}}}}

\endinput