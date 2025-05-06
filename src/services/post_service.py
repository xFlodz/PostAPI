from datetime import datetime
import grpc
from sqlalchemy import and_
from flask import jsonify
import json

from ..db import db
from ..models import Post, TagInPost, ImageInPost, VideoInPost, TextInPost
from ..utils.post_utils import save_image, generate_post_address, convert_json_date_to_sqlite_format, generate_doc_with_qr_bytes
from ..proto import user_pb2, user_pb2_grpc, tag_pb2, tag_pb2_grpc

user_channel = grpc.insecure_channel('user-api:50053') # 127.0.0.1 / user-api
user_stub = user_pb2_grpc.gRPCUserServiceStub(user_channel)

tag_channel = grpc.insecure_channel('tag-api:50054') # 127.0.0.1 / tag-api
tag_stub = tag_pb2_grpc.gRPCTagServiceStub(tag_channel)

def get_user_by_email(email):
    try:
        response = user_stub.GetUserByEmail(user_pb2.GetUserByEmailRequest(email=email))
        return {
            'id': response.id,
            'email': response.email,
            'name': response.name,
            'surname': response.surname,
            'role': response.role
        }
    except grpc.RpcError as e:
        print(f"Error fetching user by email: {e}")
        return None

def get_user_by_id(user_id):
    response = user_stub.GetUserById(user_pb2.GetUserByIdRequest(user_id=user_id))
    return {
            'id': response.id,
            'email': response.email,
            'name': response.name,
            'surname': response.surname,
            'role': response.role
        }

def get_tag_by_id(tag_id):
    try:
        response = tag_stub.GetTagById(tag_pb2.GetTagByIdRequest(tag_id=tag_id))
        return {
            'id': response.id,
            'name': response.name
        }
    except grpc.RpcError as e:
        print(f"Error fetching tag by ID: {e}")
        return None


def create_post_service(data, current_user_email):
    try:
        header = data.get('header')
        main_image = data.get('main_image')
        content = data.get('content', [])
        tags = data.get('tags', [])
        left_date = data.get('left_date')
        right_date = data.get('right_date')

        date_range = json.dumps({
            'start_date': left_date if left_date else None,
            'end_date': right_date if right_date else None
        })

        user = get_user_by_email(current_user_email)
        if not user:
            return jsonify({'error': 'Пользователь не авторизован'}), 401

        is_approved = user.get('role') == 'poster'
        creator_id = user['id']
        post_address = generate_post_address(header)
        main_image_path = save_image(main_image, post_address, 'main_image')

        new_post = Post(
            address=post_address,
            header=header,
            main_image=main_image_path,
            date_range=date_range,
            creator_id=creator_id,
            structure=json.dumps([]),
            is_approved=is_approved
        )

        db.session.add(new_post)
        db.session.commit()

        structure = []
        _add_content_to_post(new_post.id, content, post_address, structure)
        _add_tags_to_post(new_post.id, tags)
        new_post.structure = json.dumps(structure)
        db.session.commit()

        return new_post
    except Exception as e:
        db.session.rollback()
        raise e


def delete_post_service(post_address, current_user_email):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()
        user = get_user_by_email(current_user_email)

        if not post:
            return jsonify({'error': 'Пост не найден'}), 404

        if not user or user.get('role') not in ['poster', 'admin']:
            return jsonify({'error': 'У вас недостаточно прав'}), 403

        post.soft_delete()
        db.session.commit()

        return jsonify({'message': 'Пост успешно удален'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def edit_post_service(post_address, data, current_user_email):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()
        user = get_user_by_email(current_user_email)

        if not post:
            return jsonify({'error': 'Пост не найден'}), 404

        if not user or user.get('role') not in ['poster', 'admin']:
            return jsonify({'error': 'У вас недостаточно прав'}), 403

        if 'main_image' in data:
            post.main_image = save_image(data['main_image'], post.address, 'main_image')

        for key, value in data.items():
            if key not in ['main_image', 'content', 'tags']:
                setattr(post, key, value)

        ImageInPost.query.filter(ImageInPost.post_id == post.id, ImageInPost.deleted_at.is_(None)).delete()
        VideoInPost.query.filter(VideoInPost.post_id == post.id, VideoInPost.deleted_at.is_(None)).delete()
        TagInPost.query.filter(TagInPost.post_id == post.id, TagInPost.deleted_at.is_(None)).delete()
        TextInPost.query.filter(TextInPost.post_id == post.id).delete()

        db.session.commit()

        structure = []
        _add_content_to_post(post.id, data.get('content', []), post.address, structure)

        _add_tags_to_post(post.id, data.get('tags', []))

        post.structure = json.dumps(structure)
        post.address = generate_post_address(post.header)
        db.session.commit()

        return post
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def get_all_posts_service(date_filter_type=None, start_date=None, end_date=None, tags_filter=None, current_user_email=None, only_not_approved=None):
    try:
        query = Post.query.filter(Post.deleted_at.is_(None))

        if only_not_approved:
            user = get_user_by_email(only_not_approved)
            if not user or user.get('role') not in ['poster', 'admin']:
                return jsonify({'error': 'У вас недостаточно прав'}), 403
            query = query.filter(Post.is_approved == False)

        if current_user_email:
            user = get_user_by_email(current_user_email)
            if not user or user.get('role') not in ['poster', 'admin']:
                return jsonify({'error': 'У вас недостаточно прав'}), 403
            query = query.filter(Post.creator_id == user.get('id'))
        else:
            if not only_not_approved:
                query = query.filter(Post.is_approved == True)

        if start_date and end_date:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

            query = query.filter(
                and_(
                    convert_json_date_to_sqlite_format(Post.date_range, '$.start_date') >= start_date_obj.date(),
                    convert_json_date_to_sqlite_format(Post.date_range, '$.end_date') <= end_date_obj.date()
                )
            )

        if date_filter_type == 'creation':
            query = query.order_by(Post.created_at.desc())
        elif date_filter_type == 'historical':
            query = query.order_by(
                convert_json_date_to_sqlite_format(Post.date_range, '$.start_date').asc()
            )

        if tags_filter:
            tags_count = len(tags_filter)
            query = query.join(TagInPost).filter(TagInPost.tag_id.in_(tags_filter))
            query = query.group_by(Post.id).having(db.func.count(TagInPost.tag_id) == tags_count)

        posts = query.all()
        posts_list = []

        for post in posts:
            user = get_user_by_id(post.creator_id)
            author = f"{user.get('name')} {user.get('surname')}" if user else "Неизвестный автор"

            tags = [
                {'tag_id': tag_in_post.tag_id, 'tag_name': get_tag_by_id(tag_in_post.tag_id).get('name')}
                for tag_in_post in TagInPost.query.filter(TagInPost.post_id == post.id, TagInPost.deleted_at.is_(None)).all()
            ]

            text = [
                {'text': text.text}
                for text in TextInPost.query.filter(TextInPost.post_id == post.id, TextInPost.deleted_at.is_(None)).all()
            ]

            posts_list.append({
                'id': post.id,
                'address': post.address,
                'header': post.header,
                'main_image': post.main_image,
                'date_range': json.loads(post.date_range),
                'created_at': post.created_at,
                'is_approved': post.is_approved,
                'tags': tags,
                'text': text,
                'author': author
            })

        return posts_list
    except Exception as e:
        raise e



def get_post_by_address_service(post_address):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()
        if not post:
            return None

        user = get_user_by_id(post.creator_id)
        author = f'{user["name"]} {user["surname"]}' if user else 'Неизвестный автор'

        structure = json.loads(post.structure) if post.structure else []

        text = [
            {'text': text.text}
            for text in TextInPost.query.filter(TextInPost.post_id == post.id, TextInPost.deleted_at.is_(None)).all()
        ]

        images = [
            {'address': image.address, 'description': image.description}
            for image in
            ImageInPost.query.filter(ImageInPost.post_id == post.id, ImageInPost.deleted_at.is_(None)).all()
        ]

        videos = [
            {'address': video.address}
            for video in
            VideoInPost.query.filter(VideoInPost.post_id == post.id, VideoInPost.deleted_at.is_(None)).all()
        ]

        tags = [
            {'tag_id': tag.tag_id, 'tag_name': tag.tag_name}
            for tag in TagInPost.query.filter(TagInPost.post_id == post.id, TagInPost.deleted_at.is_(None)).all()
        ]

        post_data = {
            'id': post.id,
            'address': post.address,
            'header': post.header,
            'main_image': post.main_image,
            'date_range': json.loads(post.date_range),
            'structure': structure,
            'creator_id': post.creator_id,
            'author': author,
            'created_at': post.created_at,
            'is_approved': post.is_approved,
            'text': text,
            'images': images,
            'videos': videos,
            'tags': tags
        }

        return post_data
    except Exception as e:
        raise e


def approve_post_service(post_address, current_user_email):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()

        if not post:
            return {'error': 'Пост не найден'}, 404

        user = get_user_by_email(current_user_email)
        if not user or user.get('role') not in ['admin', 'poster']:
            return {'error': 'У вас недостаточно прав для одобрения поста'}, 403

        post.is_approved = True
        db.session.commit()

        return {'message': 'Пост успешно одобрен'}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500


def get_qr_code_service(post_address):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()

        if not post:
            return {'error': 'Пост не найден'}, 404

        doc = generate_doc_with_qr_bytes(post.header, post.address)
        return doc

    except Exception as e:
        return {'error': str(e)}, 500

def _add_content_to_post(post_id, content, post_address, structure):
    for item in content:
        if item['type'] == 'image':
            image_path = save_image(item['src'], post_address, 'image')
            image_in_post = ImageInPost(post_id=post_id, address=image_path, description=item.get('description', ''))
            db.session.add(image_in_post)
            structure.append({'type': 'image', 'src': image_path, 'description': item.get('description', '')})
        elif item['type'] == 'video':
            video_in_post = VideoInPost(post_id=post_id, address=item['src'])
            db.session.add(video_in_post)
            structure.append({'type': 'video', 'src': item['src']})
        elif item['type'] == 'text':
            text_in_post = TextInPost(post_id=post_id, text=item.get('value', ''))
            db.session.add(text_in_post)
            structure.append({'type': 'text', 'text': item.get('value', '')})


def _add_tags_to_post(post_id, tags):
    for tag_id in tags:
        tag = get_tag_by_id(tag_id)
        if tag:
            tag_in_post = TagInPost(post_id=post_id, tag_id=tag_id, tag_name=tag['name'])
            db.session.add(tag_in_post)
