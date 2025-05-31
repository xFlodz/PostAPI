from datetime import datetime
import grpc
from sqlalchemy import and_, or_, exists
from flask import jsonify
import json

from ..db import db
from ..models import Post, TagInPost, ImageInPost, VideoInPost, TextInPost
from ..utils.post_utils import save_image, generate_post_address, convert_json_date_to_sqlite_format, \
    generate_doc_with_qr_bytes, parse_post_dates
from ..proto import user_pb2, user_pb2_grpc, tag_pb2, tag_pb2_grpc

user_channel = grpc.insecure_channel('127.0.0.1:50053') # 127.0.0.1 / user-api
user_stub = user_pb2_grpc.gRPCUserServiceStub(user_channel)

tag_channel = grpc.insecure_channel('127.0.0.1:50054') # 127.0.0.1 / tag-api
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
        lead = data.get('lead')
        reviewer = data.get('reviewer')

        date_range = json.dumps({
            'start_date': left_date if left_date else None,
            'end_date': right_date if right_date else None
        })

        user = get_user_by_email(current_user_email)
        if not user:
            return jsonify({'error': 'Пользователь не авторизован'}), 401

        is_approved = user.get('role') == 'poster'
        creator_id = user['id']
        base_address = generate_post_address(header)
        post_address = base_address

        if Post.query.filter_by(address=post_address).first():
            counter = 1
            while Post.query.filter_by(address=post_address).first():
                post_address = f"{base_address}_{counter}"
                counter += 1

        main_image_path = save_image(main_image, post_address, 'main_image')

        new_post = Post(
            address=post_address,
            header=header,
            main_image=main_image_path,
            date_range=date_range,
            creator_id=creator_id,
            structure=json.dumps([]),
            is_approved=is_approved,
            lead = lead,
            reviewer=reviewer
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

        date_range = data['date_range']

        data['date_range'] = json.dumps({
            'start_date': date_range['start_date'] if date_range['start_date'] else None,
            'end_date': date_range['end_date'] if date_range['end_date'] else None
        })

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
        base_address = generate_post_address(post.header)
        post_address = base_address

        if Post.query.filter_by(address=post_address).first():
            counter = 1
            while Post.query.filter_by(address=post_address).first():
                post_address = f"{base_address}_{counter}"
                counter += 1
        post.address = post_address

        db.session.commit()

        return post
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def get_all_posts_service(date_filter_type=None, start_date=None, end_date=None, tags_filter=None,
                          current_user_email=None, only_not_approved=None):
    try:
        query = Post.query.filter(Post.deleted_at.is_(None))

        if only_not_approved:
            user = get_user_by_email(only_not_approved)
            if not user or user.get('role') not in ['poster', 'admin']:
                return 'У вас недостаточно прав'
            query = query.filter(Post.is_approved == False)

        if current_user_email:
            user = get_user_by_email(current_user_email)
            query = query.filter(Post.creator_id == user.get('id'))
        elif not only_not_approved:
            query = query.filter(Post.is_approved == True)

        if start_date:
            filter_start = None
            filter_end = None

            try:
                if len(start_date) == 4 and start_date.isdigit():
                    filter_start = datetime(int(start_date), 1, 1).date()
                else:
                    filter_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            except:
                pass

            if end_date:
                try:
                    if len(end_date) == 4 and end_date.isdigit():
                        filter_end = datetime(int(end_date), 12, 31).date()
                    else:
                        filter_end = datetime.strptime(end_date, "%Y-%m-%d").date()
                except:
                    pass

            if filter_start:
                posts = query.all()
                filtered_posts = []

                for post in posts:
                    post_start, post_end = parse_post_dates(post)

                    if not post_start:
                        continue

                    post_start_year_only = post_start and (post_start.month == 1 and post_start.day == 1)
                    post_end_year_only = post_end and (post_end.month == 12 and post_end.day == 31)

                    if not filter_end:
                        if post_start.year == filter_start.year:
                            filtered_posts.append(post)
                    else:
                        if post_start_year_only and (post_end is None or post_end_year_only):
                            if (post_start.year <= filter_end.year) and (
                            filter_start.year <= post_end.year if post_end else post_start.year):
                                filtered_posts.append(post)
                        else:
                            effective_post_end = post_end if post_end else post_start
                            if (post_start <= filter_end) and (effective_post_end >= filter_start):
                                filtered_posts.append(post)

                query = query.filter(Post.id.in_([p.id for p in filtered_posts]))

        if date_filter_type == 'creation':
            query = query.order_by(Post.created_at.desc())
        elif date_filter_type == 'historical':
            posts = query.all()
            posts_sorted = sorted(
                posts,
                key=lambda p: (
                    json.loads(p.date_range).get('start_date', '0000'),
                    p.created_at
                )
            )
            result = []
            for post in posts_sorted:
                user = get_user_by_id(post.creator_id)
                author = f"{user.get('name')} {user.get('surname')}" if user else "Неизвестный автор"

                tags = [
                    {'tag_id': tag_in_post.tag_id, 'tag_name': get_tag_by_id(tag_in_post.tag_id).get('name')}
                    for tag_in_post in TagInPost.query.filter(
                        TagInPost.post_id == post.id,
                        TagInPost.deleted_at.is_(None)
                    ).all()
                ]

                text = [
                    {'text': text.text}
                    for text in TextInPost.query.filter(
                        TextInPost.post_id == post.id,
                        TextInPost.deleted_at.is_(None)
                    ).all()
                ]

                result.append({
                    'id': post.id,
                    'address': post.address,
                    'header': post.header,
                    'main_image': post.main_image,
                    'date_range': json.loads(post.date_range),
                    'created_at': post.created_at,
                    'is_approved': post.is_approved,
                    'tags': tags,
                    'text': text,
                    'author': author,
                    'lead': post.lead
                })
            return result

        if tags_filter:
            tags_count = len(tags_filter)
            query = query.join(TagInPost).filter(TagInPost.tag_id.in_(tags_filter))
            query = query.group_by(Post.id).having(db.func.count(TagInPost.tag_id) == tags_count)

        result = []
        for post in query.all():
            user = get_user_by_id(post.creator_id)
            author = f"{user.get('name')} {user.get('surname')}" if user else "Неизвестный автор"

            tags = [
                {'tag_id': tag_in_post.tag_id, 'tag_name': get_tag_by_id(tag_in_post.tag_id).get('name')}
                for tag_in_post in TagInPost.query.filter(
                    TagInPost.post_id == post.id,
                    TagInPost.deleted_at.is_(None)
                ).all()
            ]

            text = [
                {'text': text.text}
                for text in TextInPost.query.filter(
                    TextInPost.post_id == post.id,
                    TextInPost.deleted_at.is_(None)
                ).all()
            ]

            result.append({
                'id': post.id,
                'address': post.address,
                'header': post.header,
                'main_image': post.main_image,
                'date_range': json.loads(post.date_range),
                'created_at': post.created_at,
                'is_approved': post.is_approved,
                'tags': tags,
                'text': text,
                'author': author,
                'lead': post.lead
            })

        return result

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
            'tags': tags,
            'lead': post.lead,
            'reviewer': post.reviewer
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


def remove_tag_from_all_posts_service(tag_id):
    try:
        TagInPost.query.filter(TagInPost.tag_id == tag_id).delete(synchronize_session=False)
        db.session.commit()
        return 1
    except Exception as e:
        db.session.rollback()
        return 0


def get_qr_code_service(post_address):
    try:
        post = Post.query.filter(Post.address == post_address, Post.deleted_at.is_(None)).first()

        if not post:
            return {'error': 'Пост не найден'}, 404

        doc = generate_doc_with_qr_bytes(post.header, post.address)
        return doc

    except Exception as e:
        return {'error': str(e)}, 500


def search_posts_service(query, date_filter_type=None, tags_filter=None, start_date=None, end_date=None):
    try:
        if not query:
            return []

        query_filter = and_(
            Post.is_approved == True,
            Post.deleted_at.is_(None)
        )

        if query:
            search_conditions = []
            words = query.split()

            for word in words:
                search_conditions.append(Post.header.ilike(f"%{word}%"))
                search_conditions.append(Post.lead.ilike(f"%{word}%"))
                search_conditions.append(Post.reviewer.ilike(f"%{word}%"))

                search_conditions.append(
                    exists().where(and_(
                        TextInPost.post_id == Post.id,
                        TextInPost.deleted_at.is_(None),
                        TextInPost.text.ilike(f"%{word}%")
                    ))
                )

                search_conditions.append(
                    exists().where(and_(
                        ImageInPost.post_id == Post.id,
                        ImageInPost.deleted_at.is_(None),
                        or_(
                            ImageInPost.description.ilike(f"%{word}%"),
                            ImageInPost.address.ilike(f"%{word}%")
                        )
                    ))
                )

            query_filter = and_(
                query_filter,
                or_(*search_conditions)
            )

        if tags_filter:
            query_filter &= exists().where(and_(
                TagInPost.post_id == Post.id,
                TagInPost.deleted_at.is_(None),
                TagInPost.tag_id.in_(tags_filter)
            ))

        if start_date or end_date:
            date_field = Post.created_at if date_filter_type == "creation" else Post.date_range
            if start_date:
                query_filter &= (date_field >= start_date)
            if end_date:
                query_filter &= (date_field <= end_date)

        posts = Post.query.filter(query_filter).all()
        return [get_post_by_address_service(post.address) for post in posts]

    except Exception as e:
        print(f"Ошибка поиска постов: {e}")
        raise


def get_search_suggestions_service(query, limit=5):
    if not query or len(query) < 2:
        return []

    try:
        query_lower = query.lower()
        suggestions = set()

        header_suggestions = Post.query.filter(
            Post.header.ilike(f"%{query}%"),
            Post.is_approved == True,
            Post.deleted_at.is_(None)
        ).limit(limit).all()

        for post in header_suggestions:
            if query_lower in post.header.lower():
                suggestions.add(post.header)

        lead_suggestions = Post.query.filter(
            Post.lead.ilike(f"%{query}%"),
            Post.is_approved == True,
            Post.deleted_at.is_(None)
        ).limit(limit).all()

        for post in lead_suggestions:
            if query_lower in post.lead.lower():
                suggestions.add(f"{post.lead[:50]}{'...' if len(post.lead) > 50 else ''}")

        reviewer_suggestions = Post.query.filter(
            Post.reviewer.ilike(f"%{query}%"),
            Post.is_approved == True,
            Post.deleted_at.is_(None)
        ).limit(limit).all()

        for post in reviewer_suggestions:
            if query_lower in post.reviewer.lower():
                suggestions.add(post.reviewer)

        text_suggestions = TextInPost.query.filter(
            TextInPost.text.ilike(f"%{query}%"),
            TextInPost.deleted_at.is_(None)
        ).limit(limit).all()

        for text in text_suggestions:
            if query_lower in text.text.lower():
                snippet = (text.text[:50] + '...') if len(text.text) > 50 else text.text
                suggestions.add(snippet)

        sorted_suggestions = sorted(
            suggestions,
            key=lambda x: (
                x.lower().startswith(query_lower),
                -x.lower().count(query_lower),
                len(x)
            ),
            reverse=True
        )

        return sorted_suggestions[:limit]

    except Exception as e:
        print(f"Ошибка при получении подсказок: {e}")
        return []


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
            print(post_id)
            tag_in_post = TagInPost(post_id=post_id, tag_id=tag_id, tag_name=tag['name'])
            db.session.add(tag_in_post)
