# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import requests
import time
import json
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    AppConfig,
    BASE_DIR as PROJECT_BASE_DIR,
    DATA_DIR as PROJECT_DATA_DIR,
    FRONTEND_DIR as PROJECT_FRONTEND_DIR,
    RESULTS_DIR as PROJECT_RESULTS_DIR,
    UPLOAD_DIR as PROJECT_UPLOAD_DIR,
)
from services.video_service import VideoManager

BASE_DIR = str(PROJECT_BASE_DIR)
FRONTEND_DIR = str(PROJECT_FRONTEND_DIR)
UPLOAD_FOLDER = str(PROJECT_UPLOAD_DIR)
RESULTS_FOLDER = str(PROJECT_RESULTS_DIR)
DATA_FOLDER = str(PROJECT_DATA_DIR)

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# 配置
CONFIG = {
    'doubao_api_url': AppConfig.DOUBAO_API_URL,
    'doubao_model': AppConfig.DOUBAO_MODEL,
    'doubao_api_token': AppConfig.DOUBAO_API_TOKEN,
    'gemini_api_url': AppConfig.GEMINI_API_URL,
    'gemini_api_token': AppConfig.GEMINI_API_TOKEN,
    'gemini_model': AppConfig.GEMINI_MODEL,
    'apify_api_token': AppConfig.APIFY_API_TOKEN
}

# 角色库和配置文件路径
ROLE_LIBRARY_FILE = os.path.join(DATA_FOLDER, 'role_library.json')
ROLE_PRESET_FILE = os.path.join(DATA_FOLDER, 'role_preset.json')
PROMPT_CONFIG_FILE = os.path.join(DATA_FOLDER, 'prompt_config.json')

# 批量任务状态存储（持久化到文件）
BATCH_TASKS_FILE = os.path.join(DATA_FOLDER, 'batch_tasks.json')

def load_batch_tasks():
    if os.path.exists(BATCH_TASKS_FILE):
        with open(BATCH_TASKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_batch_tasks(data):
    with open(BATCH_TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

batch_tasks = load_batch_tasks()
video_manager = VideoManager()

def http_request(method, url, **kwargs):
    """Send HTTP requests without inheriting system proxy environment variables."""
    with requests.Session() as session:
        session.trust_env = False
        return session.request(method=method, url=url, **kwargs)

def load_prompt_config():
    """加载提示词配置"""
    if os.path.exists(PROMPT_CONFIG_FILE):
        with open(PROMPT_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'gemini_instruction': """你是短视频角色替换策划和提示词工程师。你会收到一个参考视频，以及同一组可用替换角色资料。当前可用替换角色组编号：{role_group_number}。角色预设如下：{role_preset}。可用参考图为【@图片1】【@图片2】【@图片3】。请先完整分析输入视频的剧情、分镜、人物关系、动作、情绪、镜头节奏、场景、道具，再判断这组替换角色设定是否适合这个原视频，再输出一段严格 JSON，不要 markdown，不要解释，不要额外文本。JSON 格式固定为 {{"video_analysis":"...","character_relationships":"...","role_fit":true,"role_fit_reason":"...","role_mapping":[{{"source_role":"...","reference_image":1,"replacement_role":"...","mapping_reason":"..."}}],"replacement_prompt":"...","ratio":"9:16","duration_seconds":12.3,"character_count":2,"used_reference_images":[1,3]}}。字段要求如下：1. video_analysis 概括原视频剧情和关键分镜。2. character_relationships 说明主要登场角色关系、身份和叙事功能，人物动作，构图，绝对不要输出人物的画风相关的内容及其画面质感。3. role_fit 必须是布尔值。只有当当前角色组的人设、角色关系、年龄层、身份结构、情绪功能和原视频主要角色基本匹配，替换后仍然自然时，才返回 true；否则返回 false。4. role_fit_reason 简要说明适合或不适合的原因；如果不适合，要明确指出是人数结构不匹配、角色关系不匹配、人设冲突、年龄辈分冲突或剧情功能不匹配等哪一类问题。5. 只有 role_fit=true 时，role_mapping、character_count、used_reference_images 和 replacement_prompt 才需要完整输出；如果 role_fit=false，则 role_mapping 返回空数组，character_count 返回 0，used_reference_images 返回空数组，replacement_prompt 返回空字符串。6. role_mapping 必须明确写出原视频中需要替换的主要角色分别对应哪张参考图，以及该参考图在角色预设中的替换角色身份；reference_image 只能是 1、2、3。7. character_count 表示真正需要替换的主要人类角色数量。8. used_reference_images 表示本次实际要发送给 Seedance 的参考图编号子集，不要求连续，不要求必须把 3 张图全部用上，但必须与 role_mapping 中 reference_image 去重后的结果一致。9. 请结合剧情和角色关系，从当前角色组中选择最合适的角色来替换原视频角色，不要为了用满图片数量而强行增加角色，也不要遗漏关键主要角色。10. replacement_prompt 必须直接可用于豆包 Seedance 的参考视频角色替换任务，且只能提到 used_reference_images 里实际使用的占位符；需要清楚说明每个主要角色与哪张图片对应。11. 同一个原角色在不同镜头重复出现时，必须始终绑定同一张参考图。12. 保留原视频分镜顺序、动作、口型情绪、镜头运动、转场、视觉风格。13. 不要描述所有字幕、贴纸、UI、logo 和画面文字内容。14. 除原视频已有道具，不新增任何多余人物和道具。15. 原视频中出现的所有角色，包括Q版和小头像场景都要进行适配替换。16. replacement_prompt 必须明确要求背景统一为纯白或极简空白背景。17. replacement_prompt 紧凑但完整。18. ratio 只返回 '9:16' 的字符串。19. duration_seconds 返回视频总时长的估计值。""",
        'doubao_fixed_prompt': """固定执行要求：
0. 空白背景，生成无字幕无文字视频，绝对不要出现字幕、和其他任何文字。
1. 仔细分析原视频中的分镜数量与顺序，确保故事剧情、分镜节奏与参考视频一致。
2. 每个分镜都执行角色替换，人物形象画风、服装与参考图严格保持一致，
3. 分镜统一为静态帧，构图与参考视频完全一致，画面保持静帧不变，人物以静态呈现。
4. 每个分镜准确复刻人物的位置、互动关系、动作姿势、表情和景别，画面采用完整场景构图。
5. 道具配置严格沿用源视频各分镜中的既有道具，背景统一为 rgb(255,255,255) 的纯白色。"""
    }

def render_prompt_template(template, **values):
    """Render only known placeholders so plain JSON braces remain untouched."""
    rendered = str(template or '')
    for key, value in values.items():
        rendered = rendered.replace(f'{{{key}}}', str(value))
    return rendered

def get_user_friendly_doubao_error(status_code, body_text):
    """Translate known Doubao API errors into clear Chinese messages."""
    error_code = ''

    try:
        payload = json.loads(body_text)
        error_code = str(payload.get('error', {}).get('code') or '').strip()
    except (TypeError, ValueError, json.JSONDecodeError):
        error_code = ''

    if error_code == 'InputVideoSensitiveContentDetected.PolicyViolation':
        return '豆包风控拦截：参考视频疑似涉及版权限制，请更换可授权素材。'

    return f'豆包API返回 {status_code}: {str(body_text)[:500]}'

def save_prompt_config(config):
    """保存提示词配置"""
    with open(PROMPT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_role_library():
    """加载角色库"""
    if os.path.exists(ROLE_LIBRARY_FILE):
        with open(ROLE_LIBRARY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_role_library(roles):
    """保存角色库"""
    with open(ROLE_LIBRARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(roles, f, ensure_ascii=False, indent=2)

def load_role_preset():
    """加载角色预设"""
    if os.path.exists(ROLE_PRESET_FILE):
        with open(ROLE_PRESET_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get('preset', '')
    return ''

def save_role_preset(preset):
    """保存角色预设"""
    with open(ROLE_PRESET_FILE, 'w', encoding='utf-8') as f:
        json.dump({'preset': preset}, f, ensure_ascii=False, indent=2)

def add_to_role_library(role_images, role_preset):
    """添加角色到角色库"""
    roles = load_role_library()
    new_role = {
        'id': str(int(time.time() * 1000)),
        'images': role_images,
        'preset': role_preset,
        'created_at': datetime.now().isoformat()
    }
    roles.append(new_role)
    save_role_library(roles)
    return new_role

def _deprecated_build_gemini_instruction(role_preset, role_group_number, role_images, force_generate=False):
    instruction = build_gemini_instruction(
        role_preset,
        role_group_number,
        role_images,
        force_generate=force_generate
    )
    if not force_generate:
        return instruction

    available_refs = ', '.join([f'@image{i}' for i in range(1, len(role_images) + 1)]) or '@image1'
    force_suffix = f"""

当前是强行生成模式。你仍然要重新完整分析视频，并基于当前角色组尽可能自然地生成一套可执行的角色替换方案，不要因为适配度不足而停止输出。
额外要求：
1. 无论你最终判断是否完全适合，都必须返回完整 JSON。
2. role_mapping、character_count、used_reference_images、replacement_prompt 必须完整且可执行，不能为空。
3. 如果你仍认为不够适配，可以保留 role_fit=false，并在 role_fit_reason 里明确写风险，但仍然必须继续生成后续替换方案。
4. replacement_prompt 必须能直接进入后续生成流程，且只能引用当前实际可用的参考图：{available_refs}。
5. used_reference_images 必须只包含实际提供的参考图编号，且与 role_mapping 中的 reference_image 去重后保持一致。
"""
    return instruction + force_suffix

def _deprecated_normalize_analysis_result(analysis, role_images, force_generate=False):
    if not isinstance(analysis, dict):
        return None

    normalized = dict(analysis)
    max_ref = len(role_images)

    role_mapping = normalized.get('role_mapping')
    if not isinstance(role_mapping, list):
        role_mapping = []
    normalized['role_mapping'] = role_mapping

    used_images = normalized.get('used_reference_images')
    if not isinstance(used_images, list):
        used_images = []

    valid_used_images = []
    for value in used_images:
        try:
            idx = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= max_ref and idx not in valid_used_images:
            valid_used_images.append(idx)

    if not valid_used_images:
        for item in role_mapping:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get('reference_image'))
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= max_ref and idx not in valid_used_images:
                valid_used_images.append(idx)

    if force_generate and not valid_used_images and max_ref > 0:
        valid_used_images = [1]
    normalized['used_reference_images'] = valid_used_images

    try:
        normalized['character_count'] = int(normalized.get('character_count', 0))
    except (TypeError, ValueError):
        normalized['character_count'] = 0

    if force_generate and normalized['character_count'] <= 0:
        normalized['character_count'] = len(valid_used_images) or min(1, max_ref)

    replacement_prompt = str(normalized.get('replacement_prompt') or '').strip()
    if force_generate and not replacement_prompt and valid_used_images:
        refs_text = ', '.join([f'primary role uses image {idx}' for idx in valid_used_images])
        replacement_prompt = (
            f"Keep the original shot order, character actions, emotions, camera movement, and transitions. "
            f"Only replace roles and bind them as follows: {refs_text}. "
            "Use a pure white or minimal blank background, add no extra characters or props, and include no subtitles or other text."
        )
    normalized['replacement_prompt'] = replacement_prompt

    normalized['video_analysis'] = str(normalized.get('video_analysis') or '').strip()
    normalized['character_relationships'] = str(normalized.get('character_relationships') or '').strip()
    normalized['role_fit_reason'] = str(normalized.get('role_fit_reason') or '').strip()
    normalized['role_fit'] = bool(normalized.get('role_fit'))
    normalized['ratio'] = str(normalized.get('ratio') or '9:16')

    try:
        normalized['duration_seconds'] = float(normalized.get('duration_seconds', 12))
    except (TypeError, ValueError):
        normalized['duration_seconds'] = 12.0

    normalized['force_generate'] = force_generate
    return normalized

def _deprecated_analyze_video_with_gemini(video_url, role_images, role_preset, role_group_number, force_generate=False):
    """使用Gemini分析视频并生成替换方案"""

    prompt_config = load_prompt_config()
    instruction = render_prompt_template(
        prompt_config['gemini_instruction'],
        role_group_number=role_group_number,
        role_preset=role_preset
    )

    headers = {
        'Authorization': f"Bearer {CONFIG['gemini_api_token']}",
        'Content-Type': 'application/json'
    }

    payload = {
        'model': CONFIG['gemini_model'],
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': video_url}},
                {'type': 'text', 'text': instruction}
            ]
        }]
    }

    response = http_request('POST', CONFIG['gemini_api_url'], headers=headers, json=payload, timeout=300)
    response.raise_for_status()

    result = response.json()
    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

    # 解析JSON
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        parsed = json.loads(json_match.group(0))
        return normalize_analysis_result(parsed, role_images, force_generate=force_generate)
    return None

def create_doubao_task(video_url, role_images, analysis_result):
    """创建豆包Seedance任务"""

    video_analysis = analysis_result.get('video_analysis', '')
    structured_prompt = analysis_result.get('replacement_prompt', '')
    used_images = analysis_result.get('used_reference_images', [])

    prompt_config = load_prompt_config()
    fixed_prompt = prompt_config['doubao_fixed_prompt']

    full_prompt = f"Gemini生成剧情分析：\n{video_analysis}\n\nGemini生成角色替换提示词：\n{structured_prompt}\n\n{fixed_prompt}"

    content = [{'type': 'text', 'text': full_prompt}]

    # 添加角色图片
    for idx in used_images:
        if 1 <= idx <= len(role_images):
            content.append({
                'type': 'image_url',
                'image_url': {'url': role_images[idx-1]},
                'role': 'reference_image'
            })

    # 添加参考视频
    content.append({
        'type': 'video_url',
        'video_url': {'url': video_url},
        'role': 'reference_video'
    })

    # duration必须是整数，且限制在合理范围
    raw_duration = analysis_result.get('duration_seconds', 14)
    duration = max(4, min(14, int(round(float(raw_duration)))))
    if float(raw_duration) >= 13.5:
        duration = 14

    payload = {
        'model': CONFIG['doubao_model'],
        'content': content,
        'generate_audio': True,
        'ratio': analysis_result.get('ratio', '9:16'),
        'duration': duration,
        'watermark': False
    }

    headers = {
        'Authorization': f"Bearer {CONFIG['doubao_api_token']}",
        'Content-Type': 'application/json'
    }

    response = http_request('POST', CONFIG['doubao_api_url'], headers=headers, json=payload, timeout=300)
    result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

    if not response.ok:
        raise Exception(get_user_friendly_doubao_error(response.status_code, response.text))

    # 兼容多种响应结构提取task_id
    task_id = (
        result.get('data', {}).get('task_id') or
        result.get('data', {}).get('id') or
        result.get('task_id') or
        result.get('id') or
        ''
    )
    task_id = str(task_id).strip()

    if not task_id:
        raise Exception(f"豆包API未返回task_id，完整响应: {json.dumps(result, ensure_ascii=False)[:800]}")

    return task_id

def build_gemini_instruction(role_preset, role_group_number, role_images, force_generate=False):
    prompt_config = load_prompt_config()
    instruction = render_prompt_template(
        prompt_config['gemini_instruction'],
        role_group_number=role_group_number,
        role_preset=role_preset
    )
    if not force_generate:
        return instruction

    available_refs = ', '.join([f'@image{i}' for i in range(1, len(role_images) + 1)]) or '@image1'
    force_suffix = f"""

Force-generate mode:
1. Re-analyze the video completely and still produce an executable replacement plan.
2. Do not stop output just because the role group is not a good fit.
3. Always return complete JSON with role_mapping, character_count, used_reference_images, and replacement_prompt filled.
4. You may keep role_fit=false and explain the risk in role_fit_reason, but you must still produce a usable downstream replacement plan.
5. replacement_prompt must be directly usable for the next generation step and only reference the actually available images: {available_refs}.
6. used_reference_images must only contain valid provided image indexes and must stay consistent with role_mapping.reference_image.
"""
    return instruction + force_suffix

def normalize_analysis_result(analysis, role_images, force_generate=False):
    if not isinstance(analysis, dict):
        return None

    normalized = dict(analysis)
    max_ref = len(role_images)

    role_mapping = normalized.get('role_mapping')
    if not isinstance(role_mapping, list):
        role_mapping = []
    normalized['role_mapping'] = role_mapping

    used_images = normalized.get('used_reference_images')
    if not isinstance(used_images, list):
        used_images = []

    valid_used_images = []
    for value in used_images:
        try:
            idx = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= max_ref and idx not in valid_used_images:
            valid_used_images.append(idx)

    if not valid_used_images:
        for item in role_mapping:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get('reference_image'))
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= max_ref and idx not in valid_used_images:
                valid_used_images.append(idx)

    if force_generate and not valid_used_images and max_ref > 0:
        valid_used_images = [1]
    normalized['used_reference_images'] = valid_used_images

    try:
        normalized['character_count'] = int(normalized.get('character_count', 0))
    except (TypeError, ValueError):
        normalized['character_count'] = 0

    if force_generate and normalized['character_count'] <= 0:
        normalized['character_count'] = len(valid_used_images) or min(1, max_ref)

    replacement_prompt = str(normalized.get('replacement_prompt') or '').strip()
    if force_generate and not replacement_prompt and valid_used_images:
        refs_text = ', '.join([f'primary role uses image {idx}' for idx in valid_used_images])
        replacement_prompt = (
            f"Keep the original shot order, character actions, emotions, camera movement, and transitions. "
            f"Only replace roles and bind them as follows: {refs_text}. "
            "Use a pure white or minimal blank background, add no extra characters or props, and include no subtitles or other text."
        )
    normalized['replacement_prompt'] = replacement_prompt

    normalized['video_analysis'] = str(normalized.get('video_analysis') or '').strip()
    normalized['character_relationships'] = str(normalized.get('character_relationships') or '').strip()
    normalized['role_fit_reason'] = str(normalized.get('role_fit_reason') or '').strip()
    normalized['role_fit'] = bool(normalized.get('role_fit'))
    normalized['ratio'] = str(normalized.get('ratio') or '9:16')

    try:
        normalized['duration_seconds'] = float(normalized.get('duration_seconds', 12))
    except (TypeError, ValueError):
        normalized['duration_seconds'] = 12.0

    normalized['force_generate'] = force_generate
    return normalized

def analyze_video_with_gemini(video_url, role_images, role_preset, role_group_number, force_generate=False):
    headers = {
        'Authorization': f"Bearer {CONFIG['gemini_api_token']}",
        'Content-Type': 'application/json'
    }

    payload = {
        'model': CONFIG['gemini_model'],
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': video_url}},
                {'type': 'text', 'text': build_gemini_instruction(role_preset, role_group_number, role_images, force_generate=force_generate)}
            ]
        }]
    }

    response = http_request('POST', CONFIG['gemini_api_url'], headers=headers, json=payload, timeout=300)
    response.raise_for_status()

    result = response.json()
    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
    json_match = re.search(r'\{[\s\S]*\}', content)
    if not json_match:
        return None

    parsed = json.loads(json_match.group(0))
    return normalize_analysis_result(parsed, role_images, force_generate=force_generate)

def check_task_status(task_id):
    """查询任务状态"""
    url = f"{CONFIG['doubao_api_url']}/{task_id}"
    headers = {
        'Authorization': f"Bearer {CONFIG['doubao_api_token']}",
        'Accept': 'application/json'
    }

    response = http_request('GET', url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()

def download_video(video_url, save_path):
    """下载视频"""
    response = http_request('GET', video_url, timeout=300)
    response.raise_for_status()

    with open(save_path, 'wb') as f:
        f.write(response.content)
    return save_path

def extract_video_source(data):
    data = data or {}
    return str(
        data.get('prepared_video_url')
        or data.get('video_source')
        or data.get('video_url')
        or ''
    ).strip()

def prepare_video_for_pipeline(source):
    source = str(source or '').strip()
    if not source:
        raise ValueError('缂哄皯瑙嗛鏉ユ簮')

    public_base = AppConfig.R2_PUBLIC_BASE_URL.rstrip('/')
    if source.startswith(public_base + '/'):
        return {
            'source': source,
            'local_path': '',
            'processed_path': '',
            'public_url': source,
            'uploaded_filename': source.rsplit('/', 1)[-1],
            'duration_seconds': 0.0,
            'processed_duration_seconds': 0.0,
            'speed_factor': 1.0,
            'was_downloaded': False,
            'was_accelerated': False,
            'has_audio': False
        }

    return video_manager.prepare_source(source)

def build_upload_filename(filename):
    raw_name = os.path.basename(filename or 'video.mp4')
    stem, ext = os.path.splitext(raw_name)
    safe_stem = re.sub(r'[^A-Za-z0-9._-]+', '_', stem).strip('._') or 'video'
    safe_ext = ext or '.mp4'
    return f'{safe_stem}_{int(time.time() * 1000)}{safe_ext}'

def stream_remote_video(video_url, range_header=None):
    """Proxy remote video content for browser playback."""
    headers = {}
    if range_header:
        headers['Range'] = range_header

    remote_resp = http_request('GET', video_url, headers=headers, stream=True, timeout=300)
    remote_resp.raise_for_status()

    passthrough_headers = {}
    for name in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Cache-Control', 'ETag', 'Last-Modified']:
        value = remote_resp.headers.get(name)
        if value:
            passthrough_headers[name] = value

    if 'Accept-Ranges' not in passthrough_headers:
        passthrough_headers['Accept-Ranges'] = 'bytes'

    def generate():
        try:
            for chunk in remote_resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            remote_resp.close()

    return Response(
        stream_with_context(generate()),
        status=remote_resp.status_code,
        headers=passthrough_headers,
        direct_passthrough=True
    )

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(FRONTEND_DIR, path)

@app.route('/api/upload_local', methods=['POST'])
def upload_local():
    try:
        video_file = request.files.get('video') or request.files.get('file')
        if not video_file or not video_file.filename:
            return jsonify({'error': '缂哄皯瑙嗛鏂囦欢'}), 400

        filename = build_upload_filename(video_file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        video_file.save(save_path)

        return jsonify({
            'success': True,
            'filename': filename,
            'local_path': save_path,
            'source': save_path
        })
    except Exception as e:
        return jsonify({'error': f'鏈湴瑙嗛涓婁紶澶辫触: {str(e)}'}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """步骤1: Gemini分析视频"""
    try:
        data = request.get_json(silent=True) or {}
        source = extract_video_source(data)
        role_images = data.get('role_images', [])
        role_preset = data.get('role_preset', '')
        role_group = data.get('role_group', '1')
        force_generate = bool(data.get('force_generate'))

        if not source or not role_images:
            return jsonify({'error': '缺少必要参数'}), 400

        prepared_video = prepare_video_for_pipeline(source)
        analysis = analyze_video_with_gemini(
            prepared_video['public_url'],
            role_images,
            role_preset,
            role_group,
            force_generate=force_generate
        )

        if not analysis:
            return jsonify({'error': 'Gemini分析失败，未返回有效JSON'}), 500

        if not analysis.get('role_fit') and not force_generate:
            return jsonify({
                'success': False,
                'message': '角色不适合',
                'reason': analysis.get('role_fit_reason'),
                'analysis': analysis,
                'force_available': True,
                'prepared_video_url': prepared_video['public_url'],
                'video_processing': prepared_video
            })

        return jsonify({
            'success': True,
            'analysis': analysis,
            'forced': force_generate,
            'prepared_video_url': prepared_video['public_url'],
            'video_processing': prepared_video
        })

    except Exception as e:
        return jsonify({'error': f'Gemini分析出错: {str(e)}'}), 500

@app.route('/api/create_task', methods=['POST'])
def create_task():
    """步骤2: 创建豆包Seedance任务"""
    try:
        data = request.get_json(silent=True) or {}
        source = extract_video_source(data)
        role_images = data.get('role_images', [])
        analysis = data.get('analysis', {})

        if not source or not analysis:
            return jsonify({'error': '缺少必要参数'}), 400

        prepared_video = prepare_video_for_pipeline(source)
        task_id = create_doubao_task(prepared_video['public_url'], role_images, analysis)

        if not task_id:
            return jsonify({'error': '创建豆包任务失败，未返回task_id'}), 500

        return jsonify({
            'success': True,
            'task_id': task_id,
            'prepared_video_url': prepared_video['public_url'],
            'video_processing': prepared_video
        })

    except Exception as e:
        return jsonify({'error': f'创建豆包任务出错: {str(e)}'}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """查询任务状态"""
    try:
        status = check_task_status(task_id)
        data = status.get('data', {})
        result_obj = data.get('result', status.get('result', {}))
        task_status = data.get('status') or status.get('status') or result_obj.get('status')

        result = {
            'status': task_status,
            'data': status
        }

        if task_status == 'succeeded':
            # 兼容豆包API多种响应结构，与n8n工作流一致
            video_url = None
            candidates = [
                data.get('content', {}).get('video_url', {}).get('url') if isinstance(data.get('content', {}).get('video_url'), dict) else None,
                data.get('content', {}).get('video_url') if isinstance(data.get('content', {}).get('video_url'), str) else None,
                data.get('video_url', {}).get('url') if isinstance(data.get('video_url'), dict) else None,
                data.get('video_url') if isinstance(data.get('video_url'), str) else None,
                result_obj.get('content', {}).get('video_url', {}).get('url') if isinstance(result_obj.get('content', {}).get('video_url'), dict) else None,
                result_obj.get('content', {}).get('video_url') if isinstance(result_obj.get('content', {}).get('video_url'), str) else None,
                result_obj.get('video_url', {}).get('url') if isinstance(result_obj.get('video_url'), dict) else None,
                result_obj.get('video_url') if isinstance(result_obj.get('video_url'), str) else None,
                status.get('content', {}).get('video_url', {}).get('url') if isinstance(status.get('content', {}).get('video_url'), dict) else None,
                status.get('content', {}).get('video_url') if isinstance(status.get('content', {}).get('video_url'), str) else None,
                status.get('video_url', {}).get('url') if isinstance(status.get('video_url'), dict) else None,
                status.get('video_url') if isinstance(status.get('video_url'), str) else None,
            ]
            for c in candidates:
                if c and isinstance(c, str) and c.startswith('http'):
                    video_url = c.strip()
                    break

            result['video_url'] = video_url
            # 调试：打印完整响应便于排查
            print(f"[DEBUG] 任务成功，提取video_url={video_url}")
            print(f"[DEBUG] 豆包完整响应: {json.dumps(status, ensure_ascii=False)[:1000]}")

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download():
    """下载生成的视频"""
    try:
        data = request.get_json(silent=True) or {}
        video_url = data.get('video_url')

        if not video_url:
            return jsonify({'error': '缺少视频URL'}), 400

        filename = f"result_{int(time.time())}.mp4"
        save_path = os.path.join(RESULTS_FOLDER, filename)

        download_video(video_url, save_path)

        return jsonify({
            'success': True,
            'filename': filename,
            'path': save_path
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== 新增API：Google表格读取 =====
@app.route('/api/sheets/videos', methods=['GET'])
def get_sheet_videos():
    """从Google Sheets读取视频下载链接列"""
    try:
        sheet_id = '1Jy9rJKco-s0kcSqvy51MvdL0FfIaySDhEP1pafR1rUQ'
        gid = '1055717027'
        csv_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
        resp = http_request('GET', csv_url, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'

        import csv
        import io
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)

        if not rows:
            return jsonify({'success': True, 'videos': []})

        header = rows[0]
        # 查找"下载链接"列
        link_col = -1
        for i, h in enumerate(header):
            if '下载链接' in h or '链接' in h or 'url' in h.lower() or 'link' in h.lower():
                link_col = i
                break

        if link_col == -1:
            link_col = 0

        videos = []
        for row in rows[1:]:
            if link_col < len(row) and row[link_col].strip():
                url = row[link_col].strip()
                videos.append({
                    'url': url,
                    'label': url
                })

        return jsonify({'success': True, 'videos': videos})
    except Exception as e:
        return jsonify({'error': f'读取Google表格失败: {str(e)}'}), 500

# ===== 新增API：TikTok链接解析 =====
@app.route('/api/tiktok/resolve', methods=['POST'])
def resolve_tiktok():
    """通过Apify解析TikTok链接获取视频下载地址"""
    try:
        data = request.json
        tiktok_url = data.get('url', '').strip()
        if not tiktok_url:
            return jsonify({'error': '缺少TikTok链接'}), 400

        token = CONFIG['apify_api_token']

        # 1. 启动Apify Actor（开启视频下载），等待完成
        run_url = f'https://api.apify.com/v2/acts/clockworks~tiktok-scraper/runs?token={token}&waitForFinish=120'
        run_resp = http_request('POST', run_url, json={
            'postURLs': [tiktok_url],
            'resultsPerPage': 1,
            'shouldDownloadVideos': True,
            'shouldDownloadCovers': False
        }, timeout=150)
        run_resp.raise_for_status()
        run_data = run_resp.json().get('data', {})

        status = run_data.get('status')
        if status != 'SUCCEEDED':
            return jsonify({'error': f'Apify任务未完成，状态: {status}'}), 500

        dataset_id = run_data.get('defaultDatasetId')
        if not dataset_id:
            return jsonify({'error': 'Apify未返回数据集ID'}), 500

        # 2. 获取数据集结果
        ds_url = f'https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}'
        ds_resp = http_request('GET', ds_url, timeout=30)
        ds_resp.raise_for_status()
        items = ds_resp.json()

        if not items or not isinstance(items, list):
            return jsonify({'error': '未获取到解析结果'}), 500

        item = items[0]

        if item.get('error'):
            return jsonify({'error': f'解析失败: {item["error"]}'}), 500

        # 3. 提取视频下载链接
        # shouldDownloadVideos=true 时，链接在 videoMeta.downloadAddr 或 mediaUrls[0]
        video_url = (
            item.get('videoMeta', {}).get('downloadAddr') or
            (item.get('mediaUrls', [None]) or [None])[0] or
            ''
        )

        if not video_url:
            return jsonify({'error': '未找到视频下载链接'}), 500

        return jsonify({
            'success': True,
            'video_url': video_url,
            'title': item.get('text', ''),
            'duration': item.get('videoMeta', {}).get('duration', 0),
            'source': tiktok_url
        })

    except Exception as e:
        return jsonify({'error': f'TikTok解析出错: {str(e)}'}), 500

# ===== 新增API：角色库 =====
@app.route('/api/roles', methods=['GET'])
def get_roles():
    """获取角色库列表"""
    roles = load_role_library()
    return jsonify({'success': True, 'roles': roles})

@app.route('/api/roles', methods=['POST'])
def add_role():
    """添加角色到角色库"""
    data = request.json
    images = data.get('images', [])
    preset = data.get('preset', '')
    if not images:
        return jsonify({'error': '至少需要一张角色图片'}), 400
    role = add_to_role_library(images, preset)
    return jsonify({'success': True, 'role': role})

@app.route('/api/roles/<role_id>', methods=['DELETE'])
def delete_role(role_id):
    """删除角色"""
    roles = load_role_library()
    roles = [r for r in roles if r['id'] != role_id]
    save_role_library(roles)
    return jsonify({'success': True})

# ===== 新增API：角色预设持久化 =====
@app.route('/api/preset', methods=['GET'])
def get_preset():
    """获取保存的角色预设"""
    preset = load_role_preset()
    return jsonify({'success': True, 'preset': preset})

@app.route('/api/preset', methods=['POST'])
def save_preset():
    """保存角色预设"""
    data = request.json
    save_role_preset(data.get('preset', ''))
    return jsonify({'success': True})

# ===== 新增API：提示词配置 =====
@app.route('/api/prompt_config', methods=['GET'])
def get_prompt_config():
    """获取提示词配置"""
    config = load_prompt_config()
    return jsonify({'success': True, 'config': config})

@app.route('/api/prompt_config', methods=['POST'])
def update_prompt_config():
    """更新提示词配置"""
    data = request.json
    config = load_prompt_config()
    if 'gemini_instruction' in data:
        config['gemini_instruction'] = data['gemini_instruction']
    if 'doubao_fixed_prompt' in data:
        config['doubao_fixed_prompt'] = data['doubao_fixed_prompt']
    save_prompt_config(config)
    return jsonify({'success': True})

# ===== 新增API：批量并发任务 =====
@app.route('/api/batch_create', methods=['POST'])
def batch_create_tasks():
    """批量并发创建豆包任务"""
    try:
        data = request.get_json(silent=True) or {}
        source = extract_video_source(data)
        role_images = data.get('role_images', [])
        analysis = data.get('analysis', {})
        concurrency = min(10, max(1, int(data.get('concurrency', 1))))

        if not source or not analysis:
            return jsonify({'error': '缺少必要参数'}), 400

        prepared_video = prepare_video_for_pipeline(source)
        batch_id = str(int(time.time() * 1000))
        task_ids = []
        errors = []

        def create_single(idx):
            try:
                tid = create_doubao_task(prepared_video['public_url'], role_images, analysis)
                return {'index': idx, 'task_id': tid, 'status': 'created'}
            except Exception as e:
                return {'index': idx, 'task_id': None, 'status': 'error', 'error': str(e)}

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(create_single, i): i for i in range(concurrency)}
            for future in as_completed(futures):
                result = future.result()
                task_ids.append(result)

        task_ids.sort(key=lambda x: x['index'])
        batch_tasks[batch_id] = task_ids
        save_batch_tasks(batch_tasks)

        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'tasks': task_ids,
            'prepared_video_url': prepared_video['public_url'],
            'video_processing': prepared_video
        })

    except Exception as e:
        return jsonify({'error': f'批量创建任务出错: {str(e)}'}), 500

@app.route('/api/batch_status/<batch_id>', methods=['GET'])
def batch_status(batch_id):
    """查询批量任务状态"""
    try:
        tasks = batch_tasks.get(batch_id, [])
        if not tasks:
            return jsonify({'error': '批次不存在'}), 404

        results = []
        for t in tasks:
            if not t.get('task_id'):
                results.append(t)
                continue
            try:
                status = check_task_status(t['task_id'])
                s_data = status.get('data', {})
                result_obj = s_data.get('result', status.get('result', {}))
                task_status = s_data.get('status') or status.get('status') or result_obj.get('status')

                item = {'index': t['index'], 'task_id': t['task_id'], 'status': task_status}

                if task_status == 'succeeded':
                    video_url = None
                    for src in [s_data, result_obj, status]:
                        for path in [
                            lambda s: s.get('content', {}).get('video_url', {}).get('url') if isinstance(s.get('content', {}).get('video_url'), dict) else None,
                            lambda s: s.get('content', {}).get('video_url') if isinstance(s.get('content', {}).get('video_url'), str) else None,
                            lambda s: s.get('video_url', {}).get('url') if isinstance(s.get('video_url'), dict) else None,
                            lambda s: s.get('video_url') if isinstance(s.get('video_url'), str) else None,
                        ]:
                            v = path(src)
                            if v and isinstance(v, str) and v.startswith('http'):
                                video_url = v.strip()
                                break
                        if video_url:
                            break
                    item['video_url'] = video_url

                results.append(item)
            except Exception as e:
                results.append({'index': t['index'], 'task_id': t['task_id'], 'status': 'error', 'error': str(e)})

        return jsonify({'success': True, 'tasks': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== 调试接口 =====
@app.route('/api/video_proxy', methods=['GET'])
def video_proxy():
    """Proxy a remote video URL so browser preview does not depend on third-party embed policies."""
    try:
        video_url = request.args.get('url', '').strip()
        if not video_url:
            return jsonify({'error': '缂哄皯瑙嗛URL'}), 400
        if not re.match(r'^https?://', video_url, re.I):
            return jsonify({'error': '瑙嗛URL鏍煎紡涓嶆纭?'}), 400

        return stream_remote_video(video_url, range_header=request.headers.get('Range'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/batches', methods=['GET'])
def debug_batches():
    """列出所有批次及任务ID"""
    result = {}
    for bid, tasks in batch_tasks.items():
        result[bid] = [{'index': t['index'], 'task_id': t.get('task_id'), 'create_status': t.get('status')} for t in tasks]
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
